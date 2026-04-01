"""Approval request read-model projection (REQ-017).

Subscribes to ApprovalRequested, ApprovalRequestApproved,
ApprovalRequestRejected, and ApprovalAutoApproved events to maintain
a denormalized view of approval request status per run and stage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.projections.base import ProjectionBase

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()


class ApprovalRequestProjection(ProjectionBase):
    """Maintains pending/resolved approval status per run_id and stage."""

    def __init__(self) -> None:
        super().__init__()
        self._approvals: dict[str, dict[str, Any]] = {}

    def get_name(self) -> str:
        return "approval_request_projection"

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        """Get a single approval record."""
        return self._approvals.get(approval_id)

    def get_pending(self) -> list[dict[str, Any]]:
        """Get all pending approvals."""
        return [a for a in self._approvals.values() if a.get("status") == "pending"]

    def get_by_run_id(self, run_id: str) -> list[dict[str, Any]]:
        """Get all approvals for a given run."""
        return [a for a in self._approvals.values() if a.get("run_id") == run_id]

    async def on_approval_requested(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle ApprovalRequested — create pending record."""
        payload = envelope.payload or {}
        approval_id = payload.get("resource_id", "")
        if not approval_id:
            return
        self._approvals[approval_id] = {
            "approval_id": approval_id,
            "run_id": payload.get("run_id", ""),
            "stage": payload.get("stage", ""),
            "gate_type": payload.get("gate_type", ""),
            "status": "pending",
            "confidence": payload.get("confidence"),
            "threshold": payload.get("threshold"),
            "requested_at": envelope.occurred_at,
        }

    async def on_approval_request_created(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle ApprovalRequestCreated — create pending record."""
        payload = envelope.payload or {}
        approval_id = payload.get("resource_id", "")
        if not approval_id:
            return
        if approval_id not in self._approvals:
            self._approvals[approval_id] = {
                "approval_id": approval_id,
                "run_id": payload.get("run_id", ""),
                "stage": payload.get("stage", ""),
                "gate_type": payload.get("gate_type", ""),
                "status": "pending",
                "requested_at": envelope.occurred_at,
            }

    async def on_approval_request_approved(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle ApprovalRequestApproved — mark resolved."""
        payload = envelope.payload or {}
        approval_id = payload.get("resource_id", "")
        if approval_id in self._approvals:
            self._approvals[approval_id]["status"] = "approved"
            self._approvals[approval_id]["resolved_at"] = envelope.occurred_at

    async def on_approval_request_rejected(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle ApprovalRequestRejected — mark rejected."""
        payload = envelope.payload or {}
        approval_id = payload.get("resource_id", "")
        if approval_id in self._approvals:
            self._approvals[approval_id]["status"] = "rejected"
            self._approvals[approval_id]["resolved_at"] = envelope.occurred_at

    async def on_approval_auto_approved(
        self,
        envelope: EventEnvelope,
    ) -> None:
        """Handle ApprovalAutoApproved — record auto-approval."""
        payload = envelope.payload or {}
        approval_id = payload.get("approval_id", "")
        if not approval_id:
            return
        self._approvals[approval_id] = {
            "approval_id": approval_id,
            "run_id": payload.get("run_id", ""),
            "stage": payload.get("stage", ""),
            "gate_type": payload.get("gate_type", ""),
            "status": "auto_approved",
            "confidence": payload.get("confidence"),
            "threshold": payload.get("threshold"),
            "resolved_at": envelope.occurred_at,
        }
