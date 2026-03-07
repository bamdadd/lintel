"""Tests for WorkflowExecutor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import ThreadRef
from lintel.domain.workflow_executor import WorkflowExecutor


def _make_command() -> StartWorkflow:
    return StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature_to_pr",
    )


async def test_execute_emits_start_and_complete_events() -> None:
    event_store = AsyncMock()

    async def fake_astream(*_a: Any, **_kw: Any) -> Any:
        yield {"node_a": {"output": "done"}}

    graph = AsyncMock()
    graph.astream = fake_astream

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    run_id = await executor.execute(_make_command())

    assert isinstance(run_id, str)
    assert len(run_id) > 0

    # At least 2 event store appends: PipelineRunStarted + PipelineRunCompleted
    assert event_store.append.call_count >= 2

    # First call is PipelineRunStarted
    first_call = event_store.append.call_args_list[0]
    assert first_call.kwargs["stream_id"] == f"run:{run_id}"
    events = first_call.kwargs["events"]
    assert events[0].event_type == "PipelineRunStarted"

    # Last call is PipelineRunCompleted
    last_call = event_store.append.call_args_list[-1]
    events = last_call.kwargs["events"]
    assert events[0].event_type == "PipelineRunCompleted"


async def test_execute_emits_step_events_for_graph_chunks() -> None:
    event_store = AsyncMock()

    async def fake_astream(*_a: Any, **_kw: Any) -> Any:
        yield {"planner": {"plan": "step1"}}
        yield {"coder": {"code": "done"}}

    graph = AsyncMock()
    graph.astream = fake_astream

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    await executor.execute(_make_command())

    # Start + 2 step chunks + Complete = 4 appends
    assert event_store.append.call_count == 4


async def test_execute_emits_failed_on_error() -> None:
    event_store = AsyncMock()

    async def failing_astream(*_a: Any, **_kw: Any) -> Any:
        yield {"planner": {"plan": "step1"}}
        raise RuntimeError("graph exploded")

    graph = AsyncMock()
    graph.astream = failing_astream

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    run_id = await executor.execute(_make_command())

    # Last event should be PipelineRunFailed
    last_call = event_store.append.call_args_list[-1]
    events = last_call.kwargs["events"]
    assert events[0].event_type == "PipelineRunFailed"
