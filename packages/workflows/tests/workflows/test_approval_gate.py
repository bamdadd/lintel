"""Tests for ApprovalGateNode (REQ-F017) — confidence-based approval gates."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from lintel.workflows.nodes.approval_gate import ApprovalGateNode
from lintel.workflows.types import ApprovalDecision, ApprovalGateConfig


def _make_state(
    *,
    confidence: float = 0.0,
    pending: list[str] | None = None,
    phase: str = "planning",
) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "pending_approvals": pending or [],
        "project_id": "proj-1",
        "run_id": "run-1",
        "current_phase": phase,
    }


class TestApprovalGateConfig:
    def test_defaults(self) -> None:
        cfg = ApprovalGateConfig()
        assert cfg.confidence_threshold == 0.8
        assert cfg.timeout_seconds == 3600
        assert cfg.required_approvers == 1
        assert cfg.notification_channels == ()

    def test_custom_values(self) -> None:
        cfg = ApprovalGateConfig(
            confidence_threshold=0.95,
            timeout_seconds=600,
            required_approvers=2,
            notification_channels=("slack", "email"),
        )
        assert cfg.confidence_threshold == 0.95
        assert cfg.timeout_seconds == 600
        assert cfg.required_approvers == 2
        assert cfg.notification_channels == ("slack", "email")

    def test_frozen(self) -> None:
        cfg = ApprovalGateConfig()
        try:
            cfg.confidence_threshold = 0.5  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass


class TestApprovalDecision:
    def test_defaults(self) -> None:
        d = ApprovalDecision()
        assert d.approved is False
        assert d.approver == ""
        assert d.corrections == ""
        assert d.feedback == ""

    def test_custom(self) -> None:
        d = ApprovalDecision(
            approved=True,
            approver="alice",
            corrections="fix typo",
            feedback="looks good",
        )
        assert d.approved is True
        assert d.approver == "alice"
        assert d.corrections == "fix typo"
        assert d.feedback == "looks good"

    def test_frozen(self) -> None:
        d = ApprovalDecision(approved=True)
        try:
            d.approved = False  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass


class TestAutoApprove:
    """When confidence >= threshold, the gate should auto-approve without interrupt."""

    async def test_auto_approves_high_confidence(self) -> None:
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.8),
        )
        state = _make_state(confidence=0.9)

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert result["approval_decision"].approved is True
        assert result["approval_decision"].approver == "auto"

    async def test_auto_approve_at_exact_threshold(self) -> None:
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.8),
        )
        state = _make_state(confidence=0.8)

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert result["approval_decision"].approved is True

    async def test_auto_approve_removes_from_pending(self) -> None:
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.5),
        )
        state = _make_state(confidence=0.9, pending=["spec_approval", "pr_approval"])

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert "spec_approval" not in result["pending_approvals"]
        assert "pr_approval" in result["pending_approvals"]

    async def test_auto_approve_preserves_other_pending(self) -> None:
        node = ApprovalGateNode(
            gate_type="research_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.5),
        )
        state = _make_state(confidence=0.7, pending=["pr_approval"])

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert "pr_approval" in result["pending_approvals"]

    async def test_auto_approve_with_no_confidence_in_state(self) -> None:
        """When state has no confidence key, defaults to 0.0 — below any positive threshold."""
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.0),
        )
        state: dict[str, Any] = {
            "pending_approvals": [],
            "project_id": "proj-1",
            "run_id": "run-1",
            "current_phase": "planning",
        }

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert result["approval_decision"].approved is True


class TestHumanApprovalPath:
    """When confidence < threshold, the gate should interrupt for human approval."""

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_low_confidence_triggers_interrupt(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        mock_interrupt.return_value = {
            "approved": True,
            "approver": "alice",
            "feedback": "ok",
        }
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.8),
        )
        state = _make_state(confidence=0.5)

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        mock_interrupt.assert_called_once()
        assert isinstance(result, dict)
        decision = result["approval_decision"]
        assert isinstance(decision, ApprovalDecision)
        assert decision.approved is True
        assert decision.approver == "alice"

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_rejection_captured(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        mock_interrupt.return_value = {
            "approved": False,
            "approver": "bob",
            "corrections": "needs more tests",
            "feedback": "insufficient coverage",
        }
        node = ApprovalGateNode(
            gate_type="pr_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.9),
        )
        state = _make_state(confidence=0.3)

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        decision = result["approval_decision"]
        assert decision.approved is False
        assert decision.approver == "bob"
        assert decision.corrections == "needs more tests"
        assert result.get("corrections") == "needs more tests"

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_removes_gate_from_pending_on_resume(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        mock_interrupt.return_value = {"approved": True, "approver": "alice"}
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.9),
        )
        state = _make_state(confidence=0.1, pending=["spec_approval", "pr_approval"])

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert "spec_approval" not in result["pending_approvals"]
        assert "pr_approval" in result["pending_approvals"]

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_truthy_non_dict_input_treated_as_approval(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        mock_interrupt.return_value = True
        node = ApprovalGateNode(
            gate_type="spec_approval",
            gate_config=ApprovalGateConfig(confidence_threshold=0.9),
        )
        state = _make_state(confidence=0.1)

        result = await node(state, {"configurable": {"run_id": "run-1"}})

        assert isinstance(result, dict)
        assert result["approval_decision"].approved is True


class TestBuildPayload:
    def test_payload_includes_gate_metadata(self) -> None:
        node = ApprovalGateNode(
            gate_type="pr_approval",
            gate_config=ApprovalGateConfig(
                confidence_threshold=0.75,
                required_approvers=2,
            ),
        )
        state = _make_state(confidence=0.6)
        payload = node._build_payload(state)

        assert payload["gate_type"] == "pr_approval"
        assert payload["confidence"] == 0.6
        assert payload["confidence_threshold"] == 0.75
        assert payload["required_approvers"] == 2


class TestNodeProperties:
    def test_interrupt_type(self) -> None:
        from lintel.workflows.types import InterruptType

        node = ApprovalGateNode()
        assert node.interrupt_type == InterruptType.APPROVAL_GATE

    def test_timeout_from_config(self) -> None:
        node = ApprovalGateNode(
            gate_config=ApprovalGateConfig(timeout_seconds=1800),
        )
        assert node.timeout_seconds == 1800

    def test_on_timeout_is_escalate(self) -> None:
        node = ApprovalGateNode()
        assert node.on_timeout == "auto_escalate"

    def test_default_gate_type(self) -> None:
        node = ApprovalGateNode()
        assert node.gate_type == "spec_approval"
