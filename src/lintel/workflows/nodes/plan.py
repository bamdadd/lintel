"""Plan node: generates implementation plan via agent runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.workflows.state import ThreadWorkflowState


async def plan_work(state: ThreadWorkflowState) -> dict[str, Any]:
    """Generate work plan. v0.1: placeholder. Later: LLM agent."""
    return {
        "plan": {
            "tasks": ["Implement feature", "Write tests", "Create PR"],
            "intent": state.get("intent", "feature"),
        },
        "current_phase": "awaiting_spec_approval",
        "pending_approvals": ["spec_approval"],
    }
