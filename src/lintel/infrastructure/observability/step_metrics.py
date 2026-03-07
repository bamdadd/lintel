"""Per-step OTel metrics for workflow execution."""

from __future__ import annotations

from opentelemetry import metrics

meter = metrics.get_meter("lintel.steps")

step_duration_histogram = meter.create_histogram(
    name="lintel_step_duration_seconds",
    description="Duration of each workflow step execution",
    unit="s",
)

step_tokens_counter = meter.create_counter(
    name="lintel_step_tokens_total",
    description="Tokens consumed per step",
    unit="tokens",
)


def record_step_duration(
    workflow_id: str,
    step_type: str,
    tool_name: str,
    status: str,
    duration_s: float,
) -> None:
    """Record step execution duration."""
    step_duration_histogram.record(
        duration_s,
        attributes={
            "workflow_id": workflow_id,
            "step_type": step_type,
            "tool_name": tool_name,
            "status": status,
        },
    )


def record_step_tokens(
    workflow_id: str,
    step_type: str,
    model_id: str,
    tokens: int,
) -> None:
    """Record token consumption for a step."""
    step_tokens_counter.add(
        tokens,
        attributes={
            "workflow_id": workflow_id,
            "step_type": step_type,
            "model_id": model_id,
        },
    )
