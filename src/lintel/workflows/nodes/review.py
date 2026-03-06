"""Review node: runs code review agent on implementation output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.workflows.state import ThreadWorkflowState


async def review_output(state: ThreadWorkflowState) -> dict[str, Any]:
    """Review implementation output. v0.1: placeholder. Later: LLM agent."""
    return {
        "current_phase": "awaiting_merge_approval",
        "pending_approvals": ["merge_approval"],
        "agent_outputs": [{"role": "reviewer", "output": "LGTM"}],
    }
