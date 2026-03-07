"""Triage workflow node — classify and prioritise incoming issues."""

from __future__ import annotations

from typing import Any


async def triage_issue(state: dict[str, Any]) -> dict[str, Any]:
    """Classify issue type, severity, and route to the right agent."""
    # TODO: Wire LLM-based classification using state["sanitized_messages"]
    return {
        "current_phase": "triaging",
        "agent_outputs": [{"node": "triage", "classification": "bug", "priority": "P2"}],
    }
