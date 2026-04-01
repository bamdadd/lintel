"""Tests for ApprovalRequestProjection."""

from __future__ import annotations

from lintel.contracts.events import EventEnvelope
from lintel.projections.approval_projection import ApprovalRequestProjection


class TestApprovalRequestProjection:
    async def test_on_approval_request_created(self) -> None:
        proj = ApprovalRequestProjection()
        event = EventEnvelope(
            event_type="ApprovalRequestCreated",
            payload={
                "resource_id": "ap-1",
                "run_id": "run-1",
                "stage": "spec",
                "gate_type": "spec_approval",
            },
        )
        await proj.handle(event)
        assert proj.get_approval("ap-1") is not None
        assert proj.get_approval("ap-1")["status"] == "pending"

    async def test_on_approval_request_approved(self) -> None:
        proj = ApprovalRequestProjection()
        # Create first
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalRequestCreated",
                payload={"resource_id": "ap-2", "run_id": "run-1"},
            )
        )
        # Then approve
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalRequestApproved",
                payload={"resource_id": "ap-2"},
            )
        )
        assert proj.get_approval("ap-2")["status"] == "approved"

    async def test_on_approval_auto_approved(self) -> None:
        proj = ApprovalRequestProjection()
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalAutoApproved",
                payload={
                    "approval_id": "ap-3",
                    "run_id": "run-2",
                    "stage": "review",
                    "confidence": 0.95,
                    "threshold": 0.85,
                },
            )
        )
        record = proj.get_approval("ap-3")
        assert record is not None
        assert record["status"] == "auto_approved"

    async def test_get_pending_returns_only_pending(self) -> None:
        proj = ApprovalRequestProjection()
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalRequestCreated",
                payload={"resource_id": "p1", "run_id": "r1"},
            )
        )
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalAutoApproved",
                payload={
                    "approval_id": "p2",
                    "run_id": "r1",
                    "stage": "x",
                },
            )
        )
        pending = proj.get_pending()
        assert len(pending) == 1
        assert pending[0]["approval_id"] == "p1"

    async def test_get_by_run_id(self) -> None:
        proj = ApprovalRequestProjection()
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalRequestCreated",
                payload={"resource_id": "a1", "run_id": "r1"},
            )
        )
        await proj.handle(
            EventEnvelope(
                event_type="ApprovalRequestCreated",
                payload={"resource_id": "a2", "run_id": "r2"},
            )
        )
        results = proj.get_by_run_id("r1")
        assert len(results) == 1
