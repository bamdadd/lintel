"""Approval gate workflow node."""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


async def approval_gate(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
    *,
    gate_type: str,
) -> dict[str, Any]:
    """Gate node that sets pending approvals for human review."""
    from lintel.workflows.nodes._stage_tracking import mark_completed, mark_running

    _config = config or {}
    # Map gate_type to node name for stage tracking
    node_name = (
        "approval_gate_spec" if gate_type == "spec_approval" else "approval_gate_merge"
    )
    await mark_running(_config, node_name, state)

    project_id = state.get("project_id", "")
    existing = list(state.get("pending_approvals", []))

    if gate_type not in existing:
        existing.append(gate_type)

    logger.info(
        "approval_gate_reached",
        gate_type=gate_type,
        project_id=project_id,
    )

    await mark_completed(_config, node_name, state)
    return {"pending_approvals": existing}
