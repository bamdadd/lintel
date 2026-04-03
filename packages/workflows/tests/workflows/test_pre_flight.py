"""Tests for pre-flight validation in WorkflowExecutor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from lintel.workflows.workflow_executor import WorkflowExecutor


@dataclass(frozen=True)
class _FakeThreadRef:
    workspace_id: str = "ws"
    channel_id: str = "ch"
    thread_ts: str = "ts"


@dataclass(frozen=True)
class _FakeCommand:
    thread_ref: Any = field(default_factory=_FakeThreadRef)
    workflow_type: str = ""
    sanitized_messages: tuple[str, ...] = ()
    correlation_id: UUID = field(default_factory=uuid4)
    project_id: str = "proj-1"
    work_item_id: str = "wi-1"
    run_id: str = ""
    repo_url: str = ""
    repo_urls: tuple[str, ...] = ()
    repo_branch: str = "main"
    credential_ids: tuple[str, ...] = ()
    trigger_context: str = ""
    continue_from_run_id: str = ""


class _FakeEventStore:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append(self, stream_id: str, events: list[Any]) -> None:
        self.events.extend(events)


class TestPreFlightCheck:
    """Verify _pre_flight_check returns (errors, warnings) tuple."""

    async def test_code_workflow_without_repo_url_returns_error(self) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(workflow_type="feature", repo_url="")
        errors, warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "repository" in errors[0].lower()
        assert isinstance(warnings, list)

    async def test_code_workflow_with_repo_url_passes(self) -> None:
        app_state = AsyncMock()
        app_state.sandbox_manager = AsyncMock()
        app_state.credential_store = None

        executor = WorkflowExecutor(event_store=_FakeEventStore(), app_state=app_state)
        command = _FakeCommand(
            workflow_type="feature",
            repo_url="https://github.com/org/repo",
        )
        errors, _warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert errors == []

    async def test_non_code_workflow_without_repo_url_passes(self) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(workflow_type="summarize", repo_url="")
        errors, warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert errors == []
        assert warnings == []

    @pytest.mark.parametrize(
        "workflow_type",
        [
            "feature",
            "bug_fix",
            "code_review",
            "refactor",
            "security_audit",
            "incident_response",
            "release",
        ],
    )
    async def test_all_code_workflows_require_repo_url(self, workflow_type: str) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(workflow_type=workflow_type, repo_url="")
        errors, _warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert len(errors) >= 1

    async def test_pre_flight_failure_marks_pipeline_failed(self) -> None:
        """When pre-flight fails, execute() should emit PipelineRunFailed and return."""
        event_store = _FakeEventStore()
        executor = WorkflowExecutor(event_store=event_store)
        command = _FakeCommand(
            workflow_type="feature",
            repo_url="",
            run_id="run-preflight",
        )
        run_id = await executor.execute(command)  # type: ignore[arg-type]
        assert run_id == "run-preflight"

        event_types = [e.event_type for e in event_store.events]
        assert "WorkflowQueued" in event_types
        assert "PipelineRunFailed" in event_types

        failed_events = [e for e in event_store.events if e.event_type == "PipelineRunFailed"]
        assert len(failed_events) == 1
        assert "repository" in failed_events[0].payload["error"].lower()

    async def test_sandbox_warning_does_not_block(self) -> None:
        """Sandbox warning should not prevent pipeline dispatch."""
        executor = WorkflowExecutor(event_store=_FakeEventStore(), app_state=None)
        command = _FakeCommand(
            workflow_type="feature",
            repo_url="https://github.com/org/repo",
        )
        errors, warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert errors == []
        assert any("sandbox" in w.lower() for w in warnings)

    async def test_credential_check_via_executor(self) -> None:
        """Executor delegates credential validation to preflight module."""
        credential_store = AsyncMock()
        credential_store.get = AsyncMock(return_value=None)

        app_state = AsyncMock()
        app_state.credential_store = credential_store
        app_state.sandbox_manager = AsyncMock()

        executor = WorkflowExecutor(event_store=_FakeEventStore(), app_state=app_state)
        command = _FakeCommand(
            workflow_type="feature",
            repo_url="https://github.com/org/repo",
            credential_ids=("bad-cred",),
        )
        errors, _warnings = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "bad-cred" in errors[0]
