"""Approval gate workflow node.

This node simply records the approval in the graph state. Actual blocking
is handled by LangGraph's `interrupt_before` mechanism — the graph pauses
before this node runs, and resumes only when the approve API is called.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

GATE_TO_NODE: dict[str, str] = {
    "research_approval": "approval_gate_research",
    "spec_approval": "approval_gate_spec",
    "pr_approval": "approval_gate_pr",
}


async def approval_gate(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
    *,
    gate_type: str,
) -> dict[str, Any]:
    """Gate node — runs only after human approval resumes the graph."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config, state)
    node_name = GATE_TO_NODE.get(gate_type, f"approval_gate_{gate_type}")
    await tracker.mark_running(node_name)

    project_id = state.get("project_id", "")
    existing = list(state.get("pending_approvals", []))

    # Remove this gate from pending since we're now executing (approved)
    if gate_type in existing:
        existing.remove(gate_type)

    logger.info(
        "approval_gate_approved",
        gate_type=gate_type,
        project_id=project_id,
    )

    await tracker.mark_completed(node_name)
    return {"pending_approvals": existing}


# Alias for backward-compatible imports (e.g. from __init__.py __getattr__)
ApprovalGateNode = approval_gate
