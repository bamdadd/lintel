"""Tests for HumanInterruptNode base class and subclasses."""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import MagicMock, patch

from lintel.workflows.nodes.editable_report import EditableReportNode
from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.nodes.human_task import HumanTaskNode
from lintel.workflows.types import InterruptType, TimeoutSentinel

# --- Concrete test subclass ---


class StubInterruptNode(HumanInterruptNode):
    """Minimal concrete subclass for testing the base class."""

    @property
    def interrupt_type(self) -> InterruptType:
        return InterruptType.APPROVAL_GATE

    @property
    def timeout_seconds(self) -> int:
        return 0

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return "auto_proceed"

    async def process_resume(
        self,
        state: dict[str, Any],
        human_input: object,
    ) -> dict[str, Any]:
        return {"approved": True}


# --- Base class tests ---


class TestHumanInterruptNode:
    def test_node_name_stored(self) -> None:
        node = StubInterruptNode("my_gate")
        assert node.node_name == "my_gate"

    def test_channel_config_defaults_to_none(self) -> None:
        node = StubInterruptNode("n")
        assert node.channel_config is None

    def test_channel_config_stored(self) -> None:
        cfg = {"channel": "C123"}
        node = StubInterruptNode("n", channel_config=cfg)
        assert node.channel_config == cfg

    def test_build_payload_includes_node_info(self) -> None:
        node = StubInterruptNode("gate_1")
        state: dict[str, Any] = {"current_phase": "planning"}
        payload = node._build_payload(state)
        assert payload["node_name"] == "gate_1"
        assert payload["interrupt_type"] == "approval_gate"
        assert payload["current_phase"] == "planning"

    def test_handle_timeout_auto_proceed(self) -> None:
        node = StubInterruptNode("gate")
        sentinel = TimeoutSentinel(reason="deadline passed")
        result = node._handle_timeout({"current_phase": "plan"}, sentinel)
        assert "Auto-proceeded" in result["agent_outputs"][0]["output"]
        assert result["current_phase"] == "plan"

    def test_handle_timeout_auto_escalate(self) -> None:
        class EscalateNode(StubInterruptNode):
            @property
            def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
                return "auto_escalate"

        node = EscalateNode("gate")
        sentinel = TimeoutSentinel(reason="expired")
        result = node._handle_timeout({"current_phase": "plan"}, sentinel)
        assert "escalat" in result["current_phase"].lower() or "error" in result
        assert "Escalated" in result["agent_outputs"][0]["output"]

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_call_invokes_interrupt(self, mock_interrupt: MagicMock) -> None:
        """Calling the node should invoke LangGraph interrupt()."""
        mock_interrupt.return_value = {"approved": True}
        node = StubInterruptNode("gate")
        config: dict[str, Any] = {"configurable": {"run_id": "run-1"}}
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}

        result = await node(state, config)

        mock_interrupt.assert_called_once()
        assert result == {"approved": True}

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_call_handles_timeout_sentinel(self, mock_interrupt: MagicMock) -> None:
        """When interrupt returns a TimeoutSentinel, handle_timeout is called."""
        sentinel = TimeoutSentinel(reason="expired")
        mock_interrupt.return_value = sentinel
        node = StubInterruptNode("gate")
        config: dict[str, Any] = {"configurable": {"run_id": "run-1"}}
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}

        result = await node(state, config)

        assert "Auto-proceeded" in result["agent_outputs"][0]["output"]


# --- EditableReportNode tests ---


class TestEditableReportNode:
    def test_interrupt_type(self) -> None:
        node = EditableReportNode()
        assert node.interrupt_type == InterruptType.EDITABLE_REPORT

    def test_default_timeout(self) -> None:
        node = EditableReportNode()
        assert node.timeout_seconds == 0

    def test_custom_timeout(self) -> None:
        node = EditableReportNode(timeout=300)
        assert node.timeout_seconds == 300

    def test_build_payload_includes_report(self) -> None:
        node = EditableReportNode(report_state_key="my_report")
        state: dict[str, Any] = {
            "current_phase": "review",
            "my_report": "# Report\nSome content",
        }
        payload = node._build_payload(state)
        assert payload["report_content"] == "# Report\nSome content"
        assert payload["report_state_key"] == "my_report"

    async def test_process_resume_with_string(self) -> None:
        node = EditableReportNode(report_state_key="research_context")
        result = await node.process_resume(
            {"current_phase": "review"},
            "edited markdown",
        )
        assert result["research_context"] == "edited markdown"

    async def test_process_resume_with_dict(self) -> None:
        node = EditableReportNode(report_state_key="research_context")
        result = await node.process_resume(
            {"current_phase": "review"},
            {"content": "dict markdown"},
        )
        assert result["research_context"] == "dict markdown"


# --- HumanTaskNode tests ---


class TestHumanTaskNode:
    def test_interrupt_type(self) -> None:
        node = HumanTaskNode()
        assert node.interrupt_type == InterruptType.HUMAN_TASK

    def test_default_on_timeout_is_escalate(self) -> None:
        node = HumanTaskNode()
        assert node.on_timeout == "auto_escalate"

    def test_build_payload_includes_description(self) -> None:
        node = HumanTaskNode(task_description="Review the design")
        state: dict[str, Any] = {"current_phase": "plan"}
        payload = node._build_payload(state)
        assert payload["task_description"] == "Review the design"

    async def test_process_resume_merges_dict(self) -> None:
        node = HumanTaskNode()
        result = await node.process_resume(
            {"current_phase": "plan"},
            {"decision": "approved", "notes": "Looks good"},
        )
        assert result["decision"] == "approved"
        assert result["notes"] == "Looks good"

    async def test_process_resume_protects_internal_fields(self) -> None:
        node = HumanTaskNode()
        result = await node.process_resume(
            {"current_phase": "plan"},
            {"run_id": "hacked", "decision": "ok"},
        )
        assert "run_id" not in result
        assert result["decision"] == "ok"

    async def test_process_resume_non_dict_ignored(self) -> None:
        node = HumanTaskNode()
        result = await node.process_resume(
            {"current_phase": "plan"},
            "just a string",
        )
        # Should still return agent_outputs but no extra keys from input
        assert "agent_outputs" in result
