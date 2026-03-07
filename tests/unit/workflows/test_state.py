"""Tests for ThreadWorkflowState type definition."""

from __future__ import annotations

from typing import get_type_hints

from lintel.workflows.state import ThreadWorkflowState


class TestThreadWorkflowState:
    def test_is_typed_dict(self) -> None:
        assert hasattr(ThreadWorkflowState, "__annotations__")

    def test_required_fields_exist(self) -> None:
        hints = get_type_hints(ThreadWorkflowState)
        expected_fields = {
            "thread_ref",
            "correlation_id",
            "current_phase",
            "sanitized_messages",
            "intent",
            "plan",
            "agent_outputs",
            "pending_approvals",
            "sandbox_id",
            "sandbox_results",
            "pr_url",
            "error",
        }
        assert expected_fields.issubset(set(hints.keys()))

    def test_can_construct(self) -> None:
        state: ThreadWorkflowState = {
            "thread_ref": "t:ws:ch:ts",
            "correlation_id": "abc-123",
            "current_phase": "ingesting",
            "sanitized_messages": [],
            "intent": "",
            "plan": {},
            "agent_outputs": [],
            "pending_approvals": [],
            "sandbox_id": None,
            "sandbox_results": [],
            "pr_url": "",
            "error": None,
        }
        assert state["current_phase"] == "ingesting"
