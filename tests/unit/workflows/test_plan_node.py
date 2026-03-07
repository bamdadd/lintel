"""Tests for the plan workflow node."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from lintel.workflows.nodes.plan import _parse_plan, plan_work


class TestParsePlan:
    def test_parse_json_block(self) -> None:
        content = '```json\n{"tasks": [{"title": "Do X"}], "summary": "X"}\n```'
        result = _parse_plan(content)
        assert result["tasks"] == [{"title": "Do X"}]
        assert result["summary"] == "X"

    def test_parse_raw_json(self) -> None:
        content = '{"tasks": [{"title": "A"}], "summary": "B"}'
        result = _parse_plan(content)
        assert result["tasks"] == [{"title": "A"}]

    def test_parse_fallback(self) -> None:
        content = "Just do the thing"
        result = _parse_plan(content)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["description"] == content


class TestPlanWork:
    @pytest.fixture()
    def state(self) -> dict:
        return {
            "thread_ref": "ws/ch/ts",
            "correlation_id": "test-123",
            "current_phase": "planning",
            "sanitized_messages": ["Remove AI Providers from Projects"],
            "intent": "feature",
            "plan": {},
            "agent_outputs": [],
            "pending_approvals": [],
            "sandbox_id": None,
            "sandbox_results": [],
            "pr_url": "",
            "error": None,
        }

    async def test_stub_plan_when_no_runtime(self, state: dict) -> None:
        config = {"configurable": {}}
        result = await plan_work(state, config)
        assert result["current_phase"] == "awaiting_spec_approval"
        assert len(result["plan"]["tasks"]) == 3

    async def test_calls_agent_runtime(self, state: dict) -> None:
        plan_json = json.dumps(
            {
                "tasks": [
                    {"title": "Remove ai_provider_id from Project", "complexity": "M"},
                    {"title": "Update API routes", "complexity": "S"},
                ],
                "summary": "Remove AI Providers from Projects",
            }
        )
        runtime = AsyncMock()
        runtime.execute_step.return_value = {"content": plan_json}

        config = {"configurable": {"agent_runtime": runtime}}
        result = await plan_work(state, config)

        runtime.execute_step.assert_called_once()
        call_kwargs = runtime.execute_step.call_args.kwargs
        assert call_kwargs["agent_role"].value == "planner"
        assert call_kwargs["step_name"] == "plan_work"
        assert "Remove AI Providers" in call_kwargs["messages"][1]["content"]

        assert len(result["plan"]["tasks"]) == 2
        assert result["plan"]["intent"] == "feature"
        assert result["current_phase"] == "awaiting_spec_approval"
        assert len(result["agent_outputs"]) == 1

    async def test_empty_messages_fallback(self, state: dict) -> None:
        state["sanitized_messages"] = []
        runtime = AsyncMock()
        runtime.execute_step.return_value = {"content": '{"tasks": [], "summary": "empty"}'}

        config = {"configurable": {"agent_runtime": runtime}}
        await plan_work(state, config)

        call_kwargs = runtime.execute_step.call_args.kwargs
        assert "No description provided" in call_kwargs["messages"][1]["content"]
