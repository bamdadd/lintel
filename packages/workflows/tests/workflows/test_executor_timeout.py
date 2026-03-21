"""Unit tests for timeout handling in WorkflowExecutor."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from lintel.workflows.events import PipelineStageTimedOut
from lintel.workflows.types import StageStatus


class TestTimeoutEventEmission:
    """Verify PipelineStageTimedOut event is constructed correctly."""

    def test_timed_out_event_type(self) -> None:
        event = PipelineStageTimedOut(
            event_type="PipelineStageTimedOut",
            payload={
                "run_id": "run-1",
                "node_name": "implement",
                "timeout_seconds": 300,
            },
        )
        assert event.event_type == "PipelineStageTimedOut"
        assert event.payload["timeout_seconds"] == 300
        assert event.payload["node_name"] == "implement"


class TestStageStatusTimedOut:
    """Verify TIMED_OUT status enum value."""

    def test_timed_out_enum_value(self) -> None:
        assert StageStatus.TIMED_OUT == "timed_out"
        assert StageStatus.TIMED_OUT.value == "timed_out"

    def test_timed_out_from_string(self) -> None:
        assert StageStatus("timed_out") == StageStatus.TIMED_OUT


class TestMarkStageTimedOut:
    """Test the _executor_lifecycle.mark_stage_timed_out helper."""

    async def test_marks_stage_timed_out(self) -> None:
        """Verify that mark_stage_timed_out updates the correct stage."""

        from lintel.workflows._executor_lifecycle import mark_stage_timed_out
        from lintel.workflows.types import PipelineRun, Stage

        stages = (
            Stage(
                stage_id="s1", name="research", stage_type="research", status=StageStatus.SUCCEEDED
            ),
            Stage(
                stage_id="s2", name="implement", stage_type="implement", status=StageStatus.RUNNING
            ),
            Stage(stage_id="s3", name="review", stage_type="review", status=StageStatus.PENDING),
        )
        run = PipelineRun(
            run_id="run-1",
            project_id="proj-1",
            work_item_id="wi-1",
            workflow_definition_id="feature_to_pr",
            stages=stages,
        )

        pipeline_store = AsyncMock()
        pipeline_store.get = AsyncMock(return_value=run)
        pipeline_store.update = AsyncMock()

        app_state = MagicMock()
        app_state.pipeline_store = pipeline_store

        await mark_stage_timed_out(app_state, "run-1", "implement", 300.0)

        pipeline_store.update.assert_called_once()
        updated_run = pipeline_store.update.call_args[0][0]
        # The timed-out stage should be TIMED_OUT
        assert updated_run.stages[1].status == StageStatus.TIMED_OUT
        assert "timed out" in updated_run.stages[1].error
        # The next pending stage should be SKIPPED
        assert updated_run.stages[2].status == StageStatus.SKIPPED
        # The already-succeeded stage should be unchanged
        assert updated_run.stages[0].status == StageStatus.SUCCEEDED

    async def test_noop_when_no_app_state(self) -> None:
        """No error when app_state is None."""
        from lintel.workflows._executor_lifecycle import mark_stage_timed_out

        await mark_stage_timed_out(None, "run-1", "implement", 300.0)

    async def test_noop_when_no_pipeline_store(self) -> None:
        """No error when pipeline_store is missing."""
        from lintel.workflows._executor_lifecycle import mark_stage_timed_out

        app_state = MagicMock(spec=[])  # no pipeline_store attr
        await mark_stage_timed_out(app_state, "run-1", "implement", 300.0)


class TestStageTrackerMarkTimedOut:
    """Test StageTracker.mark_timed_out method."""

    async def test_mark_timed_out_updates_stage(self) -> None:
        from lintel.workflows.nodes._stage_tracking import StageTracker
        from lintel.workflows.types import PipelineRun, Stage

        stages = (
            Stage(
                stage_id="s1", name="research", stage_type="research", status=StageStatus.RUNNING
            ),
        )
        run = PipelineRun(
            run_id="run-1",
            project_id="proj-1",
            work_item_id="wi-1",
            workflow_definition_id="feature_to_pr",
            stages=stages,
        )

        pipeline_store = AsyncMock()
        pipeline_store.get = AsyncMock(return_value=run)
        pipeline_store.update = AsyncMock()

        config: dict[str, Any] = {
            "configurable": {
                "run_id": "run-1",
                "pipeline_store": pipeline_store,
                "app_state": None,
            }
        }

        tracker = StageTracker(config)
        await tracker.mark_timed_out("research", 120.0)

        pipeline_store.update.assert_called_once()
        updated = pipeline_store.update.call_args[0][0]
        assert updated.stages[0].status == StageStatus.TIMED_OUT
        assert "timed out" in updated.stages[0].error


class TestExecutorEnforcesStepTimeout:
    """Verify WorkflowExecutor actually cancels a slow node via asyncio.timeout."""

    async def test_slow_node_is_timed_out(self) -> None:
        """A node that exceeds its timeout is cancelled and marked TIMED_OUT."""
        from lintel.workflows.workflow_executor import WorkflowExecutor

        # Build a fake async graph that hangs forever on astream
        async def _slow_astream(
            _input: Any,  # noqa: ANN401
            *,
            config: Any = None,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            # Yield nothing — just sleep forever simulating a stuck node
            await asyncio.sleep(999)
            yield {}  # pragma: no cover — never reached

        graph_state = MagicMock()
        graph_state.next = ["implement"]

        graph = MagicMock()
        graph.astream = _slow_astream
        graph.get_state = MagicMock(return_value=graph_state)

        event_store = AsyncMock()
        event_store.append = AsyncMock()

        pipeline_store = AsyncMock()
        pipeline_store.get = AsyncMock(return_value=None)
        pipeline_store.update = AsyncMock()

        app_state = MagicMock()
        app_state.pipeline_store = pipeline_store
        app_state.workflow_definition_store = None
        app_state.settings = None
        app_state.chat_store = None
        app_state.projection_engine = None

        executor = WorkflowExecutor(
            event_store=event_store,
            graph=graph,
            app_state=app_state,
        )

        # Patch _resolve_step_timeout to return a very short timeout (0.05s)
        with patch.object(executor, "_resolve_step_timeout", AsyncMock(return_value=0.05)):
            # Store the run in suspended_runs so _stream_graph can find it
            executor._suspended_runs["run-timeout"] = {
                "graph": graph,
                "command": None,
                "stream_id": "run:run-timeout",
                "total_tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
            await executor._stream_graph(
                "run-timeout", graph, {"test": True}, {"configurable": {"thread_id": "t"}}
            )

        # Verify PipelineStageTimedOut event was emitted
        appended_events = [
            call.kwargs.get("events", call.args[1] if len(call.args) > 1 else [])
            for call in event_store.append.call_args_list
        ]
        timed_out_events = [
            e for events in appended_events for e in events if isinstance(e, PipelineStageTimedOut)
        ]
        assert len(timed_out_events) == 1
        assert timed_out_events[0].payload["node_name"] == "implement"

    async def test_fast_node_completes_normally(self) -> None:
        """A node that finishes before timeout is not affected."""
        from lintel.workflows.workflow_executor import WorkflowExecutor

        async def _fast_astream(
            _input: Any,  # noqa: ANN401
            *,
            config: Any = None,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            yield {"research": {"result": "done"}}

        graph_state = MagicMock()
        graph_state.next = []  # No interrupt

        graph = MagicMock()
        graph.astream = _fast_astream
        graph.get_state = MagicMock(return_value=graph_state)

        event_store = AsyncMock()
        event_store.append = AsyncMock()

        app_state = MagicMock()
        app_state.pipeline_store = AsyncMock()
        app_state.pipeline_store.get = AsyncMock(return_value=None)
        app_state.workflow_definition_store = None
        app_state.settings = None
        app_state.chat_store = None
        app_state.projection_engine = None

        executor = WorkflowExecutor(
            event_store=event_store,
            graph=graph,
            app_state=app_state,
        )

        with patch.object(executor, "_resolve_step_timeout", AsyncMock(return_value=10.0)):
            executor._suspended_runs["run-fast"] = {
                "graph": graph,
                "command": None,
                "stream_id": "run:run-fast",
                "total_tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
            await executor._stream_graph(
                "run-fast", graph, {"test": True}, {"configurable": {"thread_id": "t"}}
            )

        # Should have emitted PipelineStageCompleted, not PipelineStageTimedOut
        appended_events = [
            e
            for call in event_store.append.call_args_list
            for e in (call.kwargs.get("events", call.args[1] if len(call.args) > 1 else []))
        ]
        assert not any(isinstance(e, PipelineStageTimedOut) for e in appended_events)
        from lintel.workflows.events import PipelineStageCompleted

        assert any(isinstance(e, PipelineStageCompleted) for e in appended_events)
