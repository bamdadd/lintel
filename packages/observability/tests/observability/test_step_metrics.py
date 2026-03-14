"""Tests for per-step OTel metrics recording."""

from __future__ import annotations

from lintel.observability.step_metrics import (
    record_step_duration,
    record_step_tokens,
)


def test_record_step_duration_does_not_raise() -> None:
    record_step_duration(
        workflow_id="wf-1",
        step_type="agent_step",
        tool_name="",
        status="succeeded",
        duration_s=1.5,
    )


def test_record_step_tokens_does_not_raise() -> None:
    record_step_tokens(
        workflow_id="wf-1",
        step_type="agent_step",
        model_id="claude-sonnet",
        tokens=1500,
    )
