"""Ingest node: processes incoming message through PII firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.workflows.state import ThreadWorkflowState


async def ingest_message(state: ThreadWorkflowState) -> dict[str, Any]:
    """Process message. PII firewall runs before this node."""
    return {
        "current_phase": "ingesting",
        "sanitized_messages": state.get("sanitized_messages", []),
    }
