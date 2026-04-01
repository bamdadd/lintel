"""Correction record read-model projection (REQ-017).

Subscribes to AgentCorrected events and appends records to a
corrections read model for use by REQ-034 strategy improvement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.projections.base import ProjectionBase

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()


class CorrectionProjection(ProjectionBase):
    """Maintains correction records from AgentCorrected events."""

    def __init__(self) -> None:
        super().__init__()
        self._corrections: list[dict[str, Any]] = []

    def get_name(self) -> str:
        return "correction_projection"

    def get_all(self) -> list[dict[str, Any]]:
        """Get all correction records."""
        return list(self._corrections)

    def get_by_run_id(self, run_id: str) -> list[dict[str, Any]]:
        """Get corrections for a specific run."""
        return [c for c in self._corrections if c.get("run_id") == run_id]

    async def on_agent_corrected(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle AgentCorrected — append correction record."""
        payload = envelope.payload or {}
        self._corrections.append(
            {
                "approval_id": payload.get("approval_id", ""),
                "run_id": payload.get("run_id", ""),
                "stage": payload.get("stage", ""),
                "original_output": payload.get("original_output"),
                "correction": payload.get("correction"),
                "reasoning": payload.get("reasoning", ""),
                "corrected_by": payload.get("corrected_by", ""),
                "corrected_at": envelope.occurred_at,
            }
        )
