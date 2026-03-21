"""LLM cost tracker — captures token usage and cost per model call.

Provides context propagation via ``contextvars`` so that ``AgentRuntime``
can tag each LLM invocation with run_id, stage, agent_role, and project_id.
The tracker computes cost_usd via ``litellm.completion_cost`` and duration_ms
from wall-clock timing, then constructs a ``ModelCallCompleted`` event payload.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
import time
from typing import Any

# ---------------------------------------------------------------------------
# Context variables — set by AgentRuntime before each LLM call
# ---------------------------------------------------------------------------

_run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="")
_stage_var: contextvars.ContextVar[str] = contextvars.ContextVar("stage", default="")
_agent_role_var: contextvars.ContextVar[str] = contextvars.ContextVar("agent_role", default="")
_project_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("project_id", default="")


def set_cost_context(
    *,
    run_id: str = "",
    stage: str = "",
    agent_role: str = "",
    project_id: str = "",
) -> None:
    """Set context for the current LLM call.  Call before ``litellm.acompletion``."""
    _run_id_var.set(run_id)
    _stage_var.set(stage)
    _agent_role_var.set(agent_role)
    _project_id_var.set(project_id)


def clear_cost_context() -> None:
    """Reset context after an LLM call completes."""
    _run_id_var.set("")
    _stage_var.set("")
    _agent_role_var.set("")
    _project_id_var.set("")


def get_cost_context() -> dict[str, str]:
    """Read current context values (for testing or downstream use)."""
    return {
        "run_id": _run_id_var.get(),
        "stage": _stage_var.get(),
        "agent_role": _agent_role_var.get(),
        "project_id": _project_id_var.get(),
    }


# ---------------------------------------------------------------------------
# CostRecord — lightweight result of a tracked LLM call
# ---------------------------------------------------------------------------


@dataclass
class CostRecord:
    """Result of a tracked LLM call with cost and usage data."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    run_id: str
    stage: str
    agent_role: str
    project_id: str


# ---------------------------------------------------------------------------
# LLMCostTracker
# ---------------------------------------------------------------------------


class LLMCostTracker:
    """Tracks LLM call cost and token usage.

    Usage::

        tracker = LLMCostTracker()

        # Before the call:
        set_cost_context(run_id=..., stage=..., agent_role=..., project_id=...)
        start = tracker.start_timer()

        # Make the call:
        response = await litellm.acompletion(...)

        # After the call:
        record = tracker.record_call(response, start)
        clear_cost_context()

    The tracker reads context from ``contextvars`` to tag the record with
    run_id, stage, agent_role, and project_id without requiring explicit
    parameter threading.
    """

    def start_timer(self) -> float:
        """Return a monotonic start time for duration measurement."""
        return time.monotonic()

    def record_call(
        self,
        response: Any,  # noqa: ANN401
        start_time: float,
        *,
        model_override: str = "",
    ) -> CostRecord:
        """Extract usage from a litellm response and build a ``CostRecord``.

        Parameters
        ----------
        response:
            The object returned by ``litellm.acompletion``.
        start_time:
            Value from ``start_timer()`` captured before the call.
        model_override:
            If set, overrides the model name from the response.
        """
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Extract usage from response
        input_tokens = 0
        output_tokens = 0
        model_name = model_override

        if hasattr(response, "usage") and response.usage:
            input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(response.usage, "completion_tokens", 0) or 0

        if not model_name and hasattr(response, "model"):
            model_name = response.model or ""

        # Compute cost via litellm
        cost_usd = 0.0
        try:
            import litellm

            cost_usd = litellm.completion_cost(completion_response=response) or 0.0
        except Exception:
            # Fallback: cost unknown — don't let this break the flow
            pass

        ctx = get_cost_context()
        return CostRecord(
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 8),
            duration_ms=elapsed_ms,
            run_id=ctx["run_id"],
            stage=ctx["stage"],
            agent_role=ctx["agent_role"],
            project_id=ctx["project_id"],
        )

    def build_event_payload(self, record: CostRecord, **extra: Any) -> dict[str, Any]:  # noqa: ANN401
        """Build a payload dict suitable for a ``ModelCallCompleted`` event."""
        payload: dict[str, Any] = {
            "model": record.model,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": record.cost_usd,
            "duration_ms": record.duration_ms,
            "agent_role": record.agent_role,
        }
        if record.run_id:
            payload["run_id"] = record.run_id
        if record.stage:
            payload["stage"] = record.stage
        if record.project_id:
            payload["project_id"] = record.project_id
        payload.update(extra)
        return payload
