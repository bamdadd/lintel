"""Unit test: StageTimedOut event is correctly handled by projections."""

from __future__ import annotations

from lintel.workflows.events import PipelineStageTimedOut
from lintel.workflows.types import StageStatus


def test_pipeline_stage_timed_out_event_structure() -> None:
    """PipelineStageTimedOut carries the expected payload fields."""
    event = PipelineStageTimedOut(
        event_type="PipelineStageTimedOut",
        payload={
            "run_id": "run-abc",
            "node_name": "implement",
            "timeout_seconds": 300,
        },
    )
    assert event.event_type == "PipelineStageTimedOut"
    assert event.payload["run_id"] == "run-abc"
    assert event.payload["node_name"] == "implement"
    assert event.payload["timeout_seconds"] == 300


def test_stage_status_timed_out_value() -> None:
    """StageStatus.TIMED_OUT has the correct string value for projection matching."""
    assert StageStatus.TIMED_OUT == "timed_out"
    assert StageStatus("timed_out") == StageStatus.TIMED_OUT
