"""Tests for approval gate node."""

from __future__ import annotations

from lintel.workflows.nodes.approval_gate import approval_gate


class TestApprovalGate:
    async def test_auto_approves_without_store(self) -> None:
        """Without a pipeline store, the gate auto-approves immediately."""
        state = {"pending_approvals": [], "project_id": "proj-1", "run_id": ""}
        result = await approval_gate(
            state,
            gate_type="spec_approval",  # type: ignore[arg-type]
        )
        # Auto-approved: gate_type should NOT remain in pending
        assert "spec_approval" not in result["pending_approvals"]

    async def test_merge_auto_approves_without_store(self) -> None:
        state = {"pending_approvals": [], "project_id": "proj-1", "run_id": ""}
        result = await approval_gate(
            state,
            gate_type="merge_approval",  # type: ignore[arg-type]
        )
        assert "merge_approval" not in result["pending_approvals"]

    async def test_research_auto_approves_without_store(self) -> None:
        state = {"pending_approvals": [], "project_id": "proj-1", "run_id": ""}
        result = await approval_gate(
            state,
            gate_type="research_approval",  # type: ignore[arg-type]
        )
        assert "research_approval" not in result["pending_approvals"]

    async def test_preserves_other_pending_approvals(self) -> None:
        """Other pending approvals are preserved after auto-approval."""
        state = {
            "pending_approvals": ["merge_approval"],
            "project_id": "proj-1",
            "run_id": "",
        }
        result = await approval_gate(
            state,
            gate_type="spec_approval",  # type: ignore[arg-type]
        )
        assert "merge_approval" in result["pending_approvals"]
        assert "spec_approval" not in result["pending_approvals"]
