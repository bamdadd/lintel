"""Standard error handling for workflow nodes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


async def handle_node_error(
    state: Mapping[str, Any],
    node_name: str,
    error: Exception,
) -> dict[str, Any]:
    """Standard error handling for workflow nodes.

    Returns a state dict fragment that records the failure without
    setting ``current_phase`` to ``"closed"`` — this keeps the
    workflow eligible for retry from the last checkpoint.
    """
    logger.exception("node_failed", extra={"node": node_name})
    return {
        "error": f"{node_name} failed: {error}",
        "current_phase": f"{node_name}_failed",
        "agent_outputs": [
            {
                "node": node_name,
                "error": str(error),
            },
        ],
    }
