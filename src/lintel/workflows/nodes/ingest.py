"""Ingest node: processes incoming message through PII firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState


async def ingest_message(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Process message. PII firewall runs before this node."""
    from lintel.workflows.nodes._stage_tracking import mark_running

    _config = config or {}
    await mark_running(_config, "ingest", state)

    return {
        "current_phase": "ingesting",
        "sanitized_messages": state.get("sanitized_messages", []),
    }
