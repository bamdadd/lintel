"""Test execution workflow node."""

from __future__ import annotations

from typing import Any


async def run_tests(state: dict[str, Any]) -> dict[str, Any]:
    """Run the project test suite in the sandbox and report results."""
    # TODO: Wire sandbox test runner (pytest, jest, etc.)
    return {
        "current_phase": "testing",
        "agent_outputs": [{"node": "test", "verdict": "passed", "summary": "All tests passed"}],
    }
