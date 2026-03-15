"""Runtime registry for workflow nodes.

LangGraph strips custom configurable keys after interrupt/resume cycles.
This module-level registry allows nodes to look up the agent_runtime and
sandbox_manager by run_id, even when the config is empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.agents.runtime import AgentRuntime
    from lintel.sandbox.protocols import SandboxManager

_registry: dict[str, dict[str, Any]] = {}


def register(
    run_id: str,
    agent_runtime: AgentRuntime | None = None,
    sandbox_manager: SandboxManager | None = None,
    app_state: Any = None,  # noqa: ANN401
) -> None:
    """Register runtime services for a workflow run."""
    _registry[run_id] = {
        "agent_runtime": agent_runtime,
        "sandbox_manager": sandbox_manager,
        "app_state": app_state,
    }


def get_runtime(run_id: str) -> AgentRuntime | None:
    """Get the agent runtime for a run."""
    entry = _registry.get(run_id)
    return entry["agent_runtime"] if entry else None


def get_sandbox_manager(run_id: str) -> SandboxManager | None:
    """Get the sandbox manager for a run."""
    entry = _registry.get(run_id)
    return entry["sandbox_manager"] if entry else None


def get_app_state(run_id: str) -> Any:  # noqa: ANN401
    """Get the app state for a run."""
    entry = _registry.get(run_id)
    return entry["app_state"] if entry else None


def unregister(run_id: str) -> None:
    """Clean up after a workflow run completes."""
    _registry.pop(run_id, None)
