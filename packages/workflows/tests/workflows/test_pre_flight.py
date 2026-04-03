"""Tests for pre-flight validation in WorkflowExecutor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
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
    """Verify _pre_flight_check catches missing repo URL for code workflows."""

    async def test_code_workflow_without_repo_url_returns_error(self) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(workflow_type="feature", repo_url="")
        errors = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "No repository URL configured" in errors[0]
        assert "feature" in errors[0]

    async def test_code_workflow_with_repo_url_passes(self) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(
            workflow_type="feature",
            repo_url="https://github.com/org/repo",
        )
        errors = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert errors == []

    async def test_non_code_workflow_without_repo_url_passes(self) -> None:
        executor = WorkflowExecutor(event_store=_FakeEventStore())
        command = _FakeCommand(workflow_type="summarize", repo_url="")
        errors = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert errors == []

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
        errors = await executor._pre_flight_check(command)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert workflow_type in errors[0]

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

        # Should have WorkflowQueued + PipelineRunFailed events
        event_types = [e.event_type for e in event_store.events]
        assert "WorkflowQueued" in event_types
        assert "PipelineRunFailed" in event_types

        # The failed event should contain the pre-flight error message
        failed_events = [e for e in event_store.events if e.event_type == "PipelineRunFailed"]
        assert len(failed_events) == 1
        assert "No repository URL configured" in failed_events[0].payload["error"]
