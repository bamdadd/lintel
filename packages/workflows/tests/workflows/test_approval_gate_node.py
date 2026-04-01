"""Tests for ApprovalGateNode with confidence threshold logic."""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestApprovalGateNodeAutoApprove:
    """Tests for auto-approval when confidence >= threshold."""

    async def test_auto_approves_above_threshold(self) -> None:
        """When confidence >= threshold, node returns without interrupting."""
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        node = ApprovalGateNode(
            node_name="approval_gate_spec",
            gate_type="spec_approval",
        )

        state = {
            "confidence": 0.95,
            "confidence_threshold": 0.85,
            "run_id": str(uuid4()),
            "pending_approvals": ["spec_approval"],
            "current_phase": "reviewing",
            "agent_outputs": [],
        }

        # Mock the tracker to avoid pipeline store lookups
        config: dict = {"configurable": {"run_id": state["run_id"]}}

        result = await node(state, config)
        assert isinstance(result, dict)
        # spec_approval should be removed from pending
        assert "spec_approval" not in result.get("pending_approvals", [])
        # Should have an auto-approve message
        outputs = result.get("agent_outputs", [])
        assert len(outputs) > 0
        assert "Auto-approved" in str(outputs[0].get("output", ""))

    async def test_auto_approves_at_exact_threshold(self) -> None:
        """When confidence == threshold, should auto-approve."""
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        node = ApprovalGateNode(
            node_name="approval_gate",
            gate_type="spec_approval",
        )

        state = {
            "confidence": 0.85,
            "confidence_threshold": 0.85,
            "run_id": str(uuid4()),
            "pending_approvals": [],
            "current_phase": "reviewing",
            "agent_outputs": [],
        }

        config: dict = {"configurable": {"run_id": state["run_id"]}}
        result = await node(state, config)
        assert isinstance(result, dict)
        outputs = result.get("agent_outputs", [])
        assert any("Auto-approved" in str(o.get("output", "")) for o in outputs)


class TestApprovalGateNodePayload:
    """Tests for interrupt payload building."""

    def test_build_payload_includes_confidence(self) -> None:
        """Payload should include confidence, threshold, and gate_type."""
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        node = ApprovalGateNode(
            node_name="approval_gate",
            gate_type="pr_approval",
        )

        state = {
            "confidence": 0.5,
            "confidence_threshold": 0.85,
            "current_phase": "reviewing",
            "agent_outputs": [{"node": "review", "output": "looks good"}],
        }

        payload = node._build_payload(state)
        assert payload["gate_type"] == "pr_approval"
        assert payload["confidence"] == 0.5
        assert payload["threshold"] == 0.85
        assert "agent_output" in payload


class TestApprovalGateNodeResume:
    """Tests for process_resume handling."""

    async def test_approve_decision(self) -> None:
        """Approve decision should return state continuation."""
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        node = ApprovalGateNode(node_name="approval_gate")
        state = {
            "pending_approvals": ["approval_gate"],
            "current_phase": "reviewing",
        }

        result = await node.process_resume(
            state,
            {"decision": "approve", "resolved_by": "user1"},
        )
        assert "approval_gate" not in result.get("pending_approvals", [])

    async def test_reject_decision_raises(self) -> None:
        """Reject decision should raise NodeRejectedError."""
        from lintel.workflows.nodes.approval_gate import (
            ApprovalGateNode,
            NodeRejectedError,
        )

        node = ApprovalGateNode(node_name="approval_gate")
        state = {"pending_approvals": [], "current_phase": "reviewing"}

        with pytest.raises(NodeRejectedError) as exc_info:
            await node.process_resume(
                state,
                {
                    "decision": "reject",
                    "approval_id": "abc",
                    "comment": "needs work",
                },
            )
        assert "abc" in str(exc_info.value)

    async def test_correction_included_in_output(self) -> None:
        """Correction should appear in agent_outputs."""
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        node = ApprovalGateNode(node_name="approval_gate")
        state = {"pending_approvals": [], "current_phase": "reviewing"}

        correction = {"field": "summary", "new_value": "fixed"}
        result = await node.process_resume(
            state,
            {
                "decision": "approve",
                "correction": correction,
                "reasoning": "summary was wrong",
                "resolved_by": "reviewer",
            },
        )
        outputs = result.get("agent_outputs", [])
        assert len(outputs) > 0
        assert outputs[0].get("correction") == correction
