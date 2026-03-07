"""Approval gate workflow node."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)


async def approval_gate(
    state: ThreadWorkflowState,
    *,
    gate_type: str,
) -> dict[str, Any]:
    """Gate node that sets pending approvals for human review."""
    project_id = state.get("project_id", "")
    existing = list(state.get("pending_approvals", []))

    if gate_type not in existing:
        existing.append(gate_type)

    logger.info(
        "approval_gate_reached",
        gate_type=gate_type,
        project_id=project_id,
    )

    return {"pending_approvals": existing}
