"""Unit tests for HumanInterruptNode abstract base class and lifecycle."""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import AsyncMock, MagicMock, patch

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.types import InterruptRequest, InterruptType, TimeoutSentinel

# --- Concrete test subclass ---


class _TestNode(HumanInterruptNode):
    """Minimal concrete subclass used for testing the abstract base class."""

    def __init__(
        self,
        node_name: str = "test_node",
        *,
        interrupt_type: InterruptType = InterruptType.APPROVAL_GATE,
        timeout: int = 0,
        on_timeout_action: Literal["auto_proceed", "auto_escalate"] = "auto_proceed",
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_name, channel_config=channel_config)
        self._interrupt_type = interrupt_type
        self._timeout = timeout
        self._on_timeout_action = on_timeout_action

    @property
    def interrupt_type(self) -> InterruptType:
        return self._interrupt_type

    @property
    def timeout_seconds(self) -> int:
        return self._timeout

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return self._on_timeout_action

    async def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        return {"resumed": True, "input": human_input}


# --- Instantiation and properties ---


class TestConcreteSubclass:
    def test_instantiation_and_node_name(self) -> None:
        node = _TestNode("my_node")
        assert node.node_name == "my_node"

    def test_interrupt_type_property(self) -> None:
        node = _TestNode(interrupt_type=InterruptType.HUMAN_TASK)
        assert node.interrupt_type == InterruptType.HUMAN_TASK

    def test_timeout_seconds_property(self) -> None:
        node = _TestNode(timeout=120)
        assert node.timeout_seconds == 120

    def test_on_timeout_property(self) -> None:
        node = _TestNode(on_timeout_action="auto_escalate")
        assert node.on_timeout == "auto_escalate"

    def test_channel_config_defaults_none(self) -> None:
        node = _TestNode()
        assert node.channel_config is None

    def test_channel_config_stored(self) -> None:
        cfg = {"channel": "C999"}
        node = _TestNode(channel_config=cfg)
        assert node.channel_config is cfg


# --- _build_payload ---


class TestBuildPayload:
    def test_returns_correct_default_payload(self) -> None:
        node = _TestNode("gate_1", interrupt_type=InterruptType.APPROVAL_GATE)
        state: dict[str, Any] = {"current_phase": "planning"}
        payload = node._build_payload(state)

        assert payload == {
            "node_name": "gate_1",
            "interrupt_type": "approval_gate",
            "current_phase": "planning",
        }

    def test_missing_current_phase_defaults_empty(self) -> None:
        node = _TestNode("gate_2")
        payload = node._build_payload({})
        assert payload["current_phase"] == ""


# --- _handle_timeout ---


class TestHandleTimeout:
    def test_auto_proceed_returns_state_with_agent_outputs(self) -> None:
        node = _TestNode("gate", on_timeout_action="auto_proceed")
        sentinel = TimeoutSentinel(reason="deadline_exceeded")
        state: dict[str, Any] = {"current_phase": "review"}

        result = node._handle_timeout(state, sentinel)

        assert result["current_phase"] == "review"
        assert len(result["agent_outputs"]) == 1
        assert "Auto-proceeded" in result["agent_outputs"][0]["output"]
        assert "deadline_exceeded" in result["agent_outputs"][0]["output"]
        assert "error" not in result

    def test_auto_escalate_returns_error_state(self) -> None:
        node = _TestNode("gate", on_timeout_action="auto_escalate")
        sentinel = TimeoutSentinel(reason="expired")
        state: dict[str, Any] = {"current_phase": "review"}

        result = node._handle_timeout(state, sentinel)

        assert result["current_phase"] == "gate_escalated"
        assert "error" in result
        assert "timed out" in result["error"].lower()
        assert len(result["agent_outputs"]) == 1
        assert "Escalated" in result["agent_outputs"][0]["output"]


# --- __call__ lifecycle ---


class TestCallLifecycle:
    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_call_invokes_interrupt_with_request(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        """__call__ should invoke langgraph interrupt() with an InterruptRequest."""
        mock_interrupt.return_value = {"user_choice": "go"}
        node = _TestNode("gate")
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}
        config: dict[str, Any] = {"configurable": {"run_id": "run-1"}}

        await node(state, config)

        mock_interrupt.assert_called_once()
        request_arg = mock_interrupt.call_args[0][0]
        assert isinstance(request_arg, InterruptRequest)
        assert request_arg.interrupt_type == InterruptType.APPROVAL_GATE

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_resumed_with_dict_calls_process_resume(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        """When resumed with a dict, process_resume should be called."""
        resume_data = {"decision": "approved"}
        mock_interrupt.return_value = resume_data
        node = _TestNode("gate")
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}
        config: dict[str, Any] = {"configurable": {"run_id": "run-1"}}

        result = await node(state, config)

        assert result == {"resumed": True, "input": resume_data}

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_resumed_with_timeout_sentinel_uses_handle_timeout(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        """When resumed with a TimeoutSentinel, _handle_timeout is used instead."""
        sentinel = TimeoutSentinel(reason="expired")
        mock_interrupt.return_value = sentinel
        node = _TestNode("gate")
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}
        config: dict[str, Any] = {"configurable": {"run_id": "run-1"}}

        result = await node(state, config)

        assert "Auto-proceeded" in result["agent_outputs"][0]["output"]

    @patch("lintel.workflows.nodes.human_interrupt.interrupt")
    async def test_call_publishes_resumed_event(
        self,
        mock_interrupt: MagicMock,
    ) -> None:
        """After resume, the node should attempt to publish a resumed event."""
        mock_interrupt.return_value = "human says ok"
        node = _TestNode("gate")

        event_store = AsyncMock()
        config: dict[str, Any] = {
            "configurable": {"run_id": "run-1", "event_store": event_store},
        }
        state: dict[str, Any] = {"current_phase": "plan", "run_id": "run-1"}

        await node(state, config)

        event_store.append.assert_called()
