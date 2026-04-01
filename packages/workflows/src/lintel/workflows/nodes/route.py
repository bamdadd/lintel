"""Route node: classifies intent from message content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.workflows.base import WorkflowNode

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState


class RouteIntentNode(WorkflowNode):
    """Classify user intent via keyword matching. Later: LLM."""

    name: str = "route"

    async def execute(
        self,
        state: ThreadWorkflowState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        messages = state.get("sanitized_messages", [])
        combined = " ".join(messages).lower()

        intent = "feature"
        if any(word in combined for word in ["bug", "fix", "broken", "error"]):
            intent = "bug"
        elif any(word in combined for word in ["refactor", "clean", "modernize"]):
            intent = "refactor"

        return {"intent": intent, "current_phase": "planning"}


# Backward-compatible callable — existing graph registrations keep working.
route_intent = RouteIntentNode()
