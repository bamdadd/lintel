"""Analysis workflow node — examine code/context before acting."""

from __future__ import annotations

from typing import Any


async def analyse_code(state: dict[str, Any]) -> dict[str, Any]:
    """Analyse the codebase or context to inform the next step."""
    # TODO: Wire LLM-based code analysis
    return {
        "current_phase": "analysing",
        "agent_outputs": [{"node": "analyse", "summary": "Analysis complete"}],
    }
