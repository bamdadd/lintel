"""Route node: classifies intent from message content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState


async def route_intent(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Classify user intent. v0.1: keyword matching. Later: LLM."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    messages = state.get("sanitized_messages", [])
    combined = " ".join(messages).lower()

    intent = "feature"
    if any(word in combined for word in ["bug", "fix", "broken", "error"]):
        intent = "bug"
    elif any(word in combined for word in ["refactor", "clean", "modernize"]):
        intent = "refactor"

    _config = config or {}
    tracker = StageTracker(_config, state)
    await tracker.mark_completed("route")

    return {"intent": intent, "current_phase": "planning"}
