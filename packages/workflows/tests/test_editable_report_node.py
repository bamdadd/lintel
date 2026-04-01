"""Unit tests for EditableReportNode."""

from __future__ import annotations

from typing import Any

from lintel.workflows.nodes.editable_report import EditableReportNode
from lintel.workflows.types import InterruptType


class TestInterruptType:
    def test_interrupt_type_is_editable_report(self) -> None:
        node = EditableReportNode()
        assert node.interrupt_type == InterruptType.EDITABLE_REPORT


class TestBuildPayload:
    def test_includes_report_content_and_state_key(self) -> None:
        node = EditableReportNode(report_state_key="my_report")
        state: dict[str, Any] = {
            "current_phase": "review",
            "my_report": "# Draft\nSome analysis here.",
        }

        payload = node._build_payload(state)

        assert payload["report_content"] == "# Draft\nSome analysis here."
        assert payload["report_state_key"] == "my_report"
        # Also inherits base fields
        assert payload["node_name"] == "editable_report"
        assert payload["interrupt_type"] == "editable_report"
        assert payload["current_phase"] == "review"

    def test_report_content_defaults_empty_when_missing(self) -> None:
        node = EditableReportNode(report_state_key="missing_key")
        payload = node._build_payload({"current_phase": "plan"})
        assert payload["report_content"] == ""


class TestProcessResume:
    async def test_string_input_updates_state_key(self) -> None:
        node = EditableReportNode(report_state_key="research_context")
        state: dict[str, Any] = {"current_phase": "review"}

        result = await node.process_resume(state, "edited markdown content")

        assert result["research_context"] == "edited markdown content"
        assert result["current_phase"] == "review"
        assert result["agent_outputs"][0]["node"] == "editable_report"

    async def test_dict_input_extracts_content_field(self) -> None:
        node = EditableReportNode(report_state_key="research_context")
        state: dict[str, Any] = {"current_phase": "review"}

        result = await node.process_resume(state, {"content": "dict markdown"})

        assert result["research_context"] == "dict markdown"

    async def test_dict_input_missing_content_defaults_empty(self) -> None:
        node = EditableReportNode()
        result = await node.process_resume({"current_phase": "x"}, {})
        assert result["research_context"] == ""

    async def test_non_string_non_dict_converts_to_string(self) -> None:
        node = EditableReportNode(report_state_key="research_context")
        state: dict[str, Any] = {"current_phase": "review"}

        result = await node.process_resume(state, 42)

        assert result["research_context"] == "42"

    async def test_non_string_non_dict_with_list(self) -> None:
        node = EditableReportNode()
        result = await node.process_resume({"current_phase": "x"}, ["a", "b"])
        assert result["research_context"] == "['a', 'b']"


class TestReportStateKey:
    def test_default_report_state_key(self) -> None:
        node = EditableReportNode()
        assert node._report_state_key == "research_context"

    def test_custom_report_state_key(self) -> None:
        node = EditableReportNode(report_state_key="custom_report")
        assert node._report_state_key == "custom_report"

    async def test_custom_key_used_in_resume(self) -> None:
        node = EditableReportNode(report_state_key="final_report")
        result = await node.process_resume({"current_phase": "done"}, "content")
        assert "final_report" in result
        assert result["final_report"] == "content"

    def test_custom_key_used_in_payload(self) -> None:
        node = EditableReportNode(report_state_key="summary")
        state: dict[str, Any] = {"current_phase": "x", "summary": "text"}
        payload = node._build_payload(state)
        assert payload["report_state_key"] == "summary"
        assert payload["report_content"] == "text"


class TestDefaults:
    def test_default_node_name(self) -> None:
        node = EditableReportNode()
        assert node.node_name == "editable_report"

    def test_default_timeout_is_zero(self) -> None:
        node = EditableReportNode()
        assert node.timeout_seconds == 0

    def test_default_on_timeout_is_auto_proceed(self) -> None:
        node = EditableReportNode()
        assert node.on_timeout == "auto_proceed"

    def test_custom_timeout(self) -> None:
        node = EditableReportNode(timeout=600)
        assert node.timeout_seconds == 600

    def test_custom_on_timeout_action(self) -> None:
        node = EditableReportNode(on_timeout_action="auto_escalate")
        assert node.on_timeout == "auto_escalate"
