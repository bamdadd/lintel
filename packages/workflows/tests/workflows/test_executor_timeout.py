"""Unit tests for timeout handling in WorkflowExecutor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
