"""Tests for WorkflowExecutor pre-flight checks."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from lintel.contracts.types import ThreadRef
from lintel.workflows.commands import StartWorkflow
from lintel.workflows.workflow_executor import WorkflowExecutor


def _make_graph() -> MagicMock:
    async def fake_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
        yield {"node_a": {"output": "done"}}

    graph = MagicMock()
    graph.astream = fake_astream
    state = MagicMock()
    state.next = ()
    graph.get_state = MagicMock(return_value=state)
    return graph


# ── repo URL checks ──────────────────────────────────────────────────


async def test_preflight_blocks_code_workflow_without_repo_url() -> None:
    """Code workflows without a repo URL should fail immediately."""
    event_store = AsyncMock()
    graph = _make_graph()

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="",
    )
    await executor.execute(command)

    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunFailed" in all_events
    assert "PipelineRunStarted" not in all_events


async def test_preflight_allows_code_workflow_with_repo_url() -> None:
    """Code workflows with a repo URL should proceed normally."""
    event_store = AsyncMock()
    graph = _make_graph()

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="https://github.com/org/repo",
    )
    await executor.execute(command)

    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunStarted" in all_events
    assert "PipelineRunCompleted" in all_events


async def test_preflight_allows_non_code_workflow_without_repo_url() -> None:
    """Non-code workflows (e.g. summarize) don't require a repo URL."""
    event_store = AsyncMock()
    graph = _make_graph()

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="summarize",
        repo_url="",
    )
    await executor.execute(command)

    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunStarted" in all_events


# ── credential checks ────────────────────────────────────────────────


async def test_preflight_blocks_when_credential_not_found() -> None:
    """If credential_ids reference non-existent credentials, block the pipeline."""
    event_store = AsyncMock()
    graph = _make_graph()

    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=None)

    app_state = MagicMock()
    app_state.credential_store = credential_store
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = None
    app_state.sandbox_manager = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="https://github.com/org/repo",
        credential_ids=("cred-missing",),
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunFailed" in all_events
    assert "PipelineRunStarted" not in all_events


async def test_preflight_passes_when_credentials_exist() -> None:
    """Valid credential_ids should not block the pipeline."""
    event_store = AsyncMock()
    graph = _make_graph()

    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value={"credential_id": "cred-1", "name": "gh-token"})

    app_state = MagicMock()
    app_state.credential_store = credential_store
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = None
    app_state.sandbox_manager = MagicMock()  # present so no warning blocks

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="https://github.com/org/repo",
        credential_ids=("cred-1",),
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunStarted" in all_events


async def test_preflight_no_credentials_skips_check() -> None:
    """When no credential_ids are provided, the credential check is skipped."""
    event_store = AsyncMock()
    graph = _make_graph()

    credential_store = AsyncMock()
    app_state = MagicMock()
    app_state.credential_store = credential_store
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = None
    app_state.sandbox_manager = MagicMock()

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="https://github.com/org/repo",
        credential_ids=(),
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    credential_store.get.assert_not_called()
    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunStarted" in all_events


# ── sandbox availability (warning, not blocking) ─────────────────────


async def test_preflight_warns_when_no_sandbox_manager() -> None:
    """Missing sandbox_manager logs a warning but does not block."""
    event_store = AsyncMock()
    graph = _make_graph()

    app_state = MagicMock()
    app_state.credential_store = None
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = None
    app_state.sandbox_manager = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="https://github.com/org/repo",
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    # Should proceed despite no sandbox_manager (warning only)
    all_events = [
        e.event_type for call in event_store.append.call_args_list for e in call.kwargs["events"]
    ]
    assert "PipelineRunStarted" in all_events


# ── pre-flight failure marks work item failed ────────────────────────


async def test_preflight_failure_marks_work_item_failed() -> None:
    """Pre-flight failure should set work item status to 'failed'."""
    event_store = AsyncMock()
    graph = _make_graph()

    work_item = {"work_item_id": "wi-1", "status": "in_progress"}
    work_item_store = AsyncMock()
    work_item_store.get = AsyncMock(return_value=work_item)

    app_state = MagicMock()
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = work_item_store
    app_state.credential_store = None
    app_state.sandbox_manager = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="",
        work_item_id="wi-1",
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    work_item_store.get.assert_called_once_with("wi-1")
    assert work_item["status"] == "failed"


# ── multiple errors combined ─────────────────────────────────────────


async def test_preflight_combines_multiple_errors() -> None:
    """When multiple checks fail, all errors should appear in the failure event."""
    event_store = AsyncMock()
    graph = _make_graph()

    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=None)

    app_state = MagicMock()
    app_state.credential_store = credential_store
    app_state.pipeline_store = None
    app_state.chat_store = None
    app_state.work_item_store = None
    app_state.sandbox_manager = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature",
        repo_url="",  # missing repo
        credential_ids=("cred-bad",),  # missing credential
    )

    executor = WorkflowExecutor(event_store=event_store, graph=graph, app_state=app_state)
    await executor.execute(command)

    # Find the PipelineRunFailed event
    failed_events = [
        e
        for call in event_store.append.call_args_list
        for e in call.kwargs["events"]
        if e.event_type == "PipelineRunFailed"
    ]
    assert len(failed_events) == 1
    error_msg = failed_events[0].payload["error"]
    assert "repository url" in error_msg.lower()
    assert "cred-bad" in error_msg
