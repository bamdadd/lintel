"""Tests for WorkflowExecutor."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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

    async def fake_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
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

    async def fake_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
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

    async def failing_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
        yield {"planner": {"plan": "step1"}}
        raise RuntimeError("graph exploded")

    graph = AsyncMock()
    graph.astream = failing_astream

    executor = WorkflowExecutor(event_store=event_store, graph=graph)
    await executor.execute(_make_command())

    # Last event should be PipelineRunFailed
    last_call = event_store.append.call_args_list[-1]
    events = last_call.kwargs["events"]
    assert events[0].event_type == "PipelineRunFailed"


async def test_execute_marks_work_item_failed_on_error() -> None:
    """REQ-1.2: Work item status set to 'failed' when workflow fails."""
    event_store = AsyncMock()

    async def failing_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
        raise RuntimeError("boom")

    graph = AsyncMock()
    graph.astream = failing_astream

    work_item = {"work_item_id": "wi-1", "status": "in_progress"}
    work_item_store = AsyncMock()
    work_item_store.get = AsyncMock(return_value=work_item)

    app_state = AsyncMock()
    app_state.work_item_store = work_item_store
    app_state.pipeline_store = None
    app_state.chat_store = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature_to_pr",
        work_item_id="wi-1",
    )

    executor = WorkflowExecutor(
        event_store=event_store, graph=graph, app_state=app_state,
    )
    await executor.execute(command)

    work_item_store.get.assert_called_once_with("wi-1")
    work_item_store.update.assert_called_once_with("wi-1", work_item)
    assert work_item["status"] == "failed"


async def test_execute_marks_running_stages_failed_on_error() -> None:
    """Running stages should be marked failed when the workflow errors."""
    from dataclasses import replace as dc_replace

    from lintel.contracts.types import PipelineRun, PipelineStatus, Stage, StageStatus

    event_store = AsyncMock()

    async def failing_astream(*_a: object, **_kw: object) -> AsyncGenerator[dict[str, object]]:
        raise RuntimeError("model not found")

    graph = AsyncMock()
    graph.astream = failing_astream

    # Create a pipeline run with one stage in running status
    stages = (
        Stage(stage_id="s1", name="plan", stage_type="plan", status=StageStatus.RUNNING),
        Stage(stage_id="s2", name="implement", stage_type="implement", status=StageStatus.PENDING),
    )
    run = PipelineRun(
        run_id="test-run",
        project_id="p1",
        work_item_id="wi-1",
        workflow_definition_id="feature_to_pr",
        status=PipelineStatus.RUNNING,
        stages=stages,
    )

    pipeline_store = AsyncMock()
    pipeline_store.get = AsyncMock(return_value=run)
    updated_runs: list[PipelineRun] = []

    async def capture_update(updated: PipelineRun) -> None:
        updated_runs.append(updated)

    pipeline_store.update = AsyncMock(side_effect=capture_update)

    app_state = AsyncMock()
    app_state.pipeline_store = pipeline_store
    app_state.work_item_store = None
    app_state.chat_store = None
    app_state.sandbox_manager = None
    app_state.credential_store = None
    app_state.code_artifact_store = None
    app_state.test_result_store = None

    command = StartWorkflow(
        thread_ref=ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="ts1"),
        workflow_type="feature_to_pr",
        run_id="test-run",
    )

    executor = WorkflowExecutor(
        event_store=event_store, graph=graph, app_state=app_state,
    )
    await executor.execute(command)

    # Find the update that marks running stages as failed
    assert len(updated_runs) >= 1
    # The last few updates include _mark_running_stages_failed and _update_pipeline_status
    # Find the one where a stage has FAILED status
    failed_update = None
    for u in updated_runs:
        if any(s.status == StageStatus.FAILED for s in u.stages):
            failed_update = u
            break
    assert failed_update is not None, (
        f"No update found with failed stages. Updates: "
        f"{[(s.name, s.status) for u in updated_runs for s in u.stages]}"
    )
    failed_stages = [s for s in failed_update.stages if s.status == StageStatus.FAILED]
    assert len(failed_stages) == 1
    assert failed_stages[0].name == "plan"
    assert failed_stages[0].error  # has an error message
