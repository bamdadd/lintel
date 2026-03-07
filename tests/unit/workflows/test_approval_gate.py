"""Tests for approval gate node."""

from __future__ import annotations

from lintel.workflows.nodes.approval_gate import approval_gate


class TestApprovalGate:
    async def test_spec_approval_sets_pending(self) -> None:
        state = {"pending_approvals": [], "project_id": "proj-1"}
        result = await approval_gate(
            state, gate_type="spec_approval",  # type: ignore[arg-type]
        )
        assert "spec_approval" in result["pending_approvals"]

    async def test_merge_approval_sets_pending(self) -> None:
        state = {"pending_approvals": [], "project_id": "proj-1"}
        result = await approval_gate(
            state, gate_type="merge_approval",  # type: ignore[arg-type]
        )
        assert "merge_approval" in result["pending_approvals"]

    async def test_no_duplicates(self) -> None:
        state = {
            "pending_approvals": ["spec_approval"],
            "project_id": "proj-1",
        }
        result = await approval_gate(
            state, gate_type="spec_approval",  # type: ignore[arg-type]
        )
        assert result["pending_approvals"].count("spec_approval") == 1

    async def test_appends_to_existing(self) -> None:
        state = {
            "pending_approvals": ["spec_approval"],
            "project_id": "proj-1",
        }
        result = await approval_gate(
            state, gate_type="merge_approval",  # type: ignore[arg-type]
        )
        assert "spec_approval" in result["pending_approvals"]
        assert "merge_approval" in result["pending_approvals"]

    async def test_missing_project_id(self) -> None:
        state = {"pending_approvals": []}
        result = await approval_gate(
            state, gate_type="spec_approval",  # type: ignore[arg-type]
        )
        assert "spec_approval" in result["pending_approvals"]
