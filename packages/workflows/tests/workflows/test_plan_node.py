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
        assert result is not None
        assert result["tasks"] == [{"title": "Do X"}]
        assert result["summary"] == "X"

    def test_parse_raw_json(self) -> None:
        content = '{"tasks": [{"title": "A"}], "summary": "B"}'
        result = _parse_plan(content)
        assert result is not None
        assert result["tasks"] == [{"title": "A"}]

    def test_parse_unparseable_returns_none(self) -> None:
        content = "Just do the thing"
        result = _parse_plan(content)
        assert result is None

    def test_parse_narration_returns_none(self) -> None:
        content = "Let me think about this. First I'll read the files..."
        result = _parse_plan(content)
        assert result is None


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
                    {
                        "title": "Remove ai_provider_id from Project",
                        "description": "Remove the field from the dataclass",
                        "file_paths": ["src/models/project.py"],
                        "complexity": "M",
                    },
                    {
                        "title": "Update API routes",
                        "description": "Remove provider references from routes",
                        "file_paths": ["src/api/routes.py"],
                        "complexity": "S",
                    },
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

    async def test_unparseable_output_fails(self, state: dict) -> None:
        runtime = AsyncMock()
        runtime.execute_step.return_value = {"content": "Let me think about this..."}

        config = {"configurable": {"agent_runtime": runtime}}
        result = await plan_work(state, config)

        assert result["current_phase"] == "failed"
        assert "parse" in result["error"].lower()

    async def test_invalid_plan_retries_then_fails(self, state: dict) -> None:
        """Single-task plan triggers retry; if retry also fails, stage fails."""
        bad_plan = json.dumps({"tasks": [{"title": "Do all"}], "summary": "Everything"})
        runtime = AsyncMock()
        runtime.execute_step.return_value = {"content": bad_plan}

        config = {"configurable": {"agent_runtime": runtime}}
        result = await plan_work(state, config)

        # Should have called execute_step twice (initial + retry)
        assert runtime.execute_step.call_count == 2
        assert result["current_phase"] == "failed"

    async def test_invalid_plan_retry_succeeds(self, state: dict) -> None:
        """Invalid plan triggers retry; retry produces valid plan."""
        bad_plan = json.dumps({"tasks": [{"title": "Do all"}], "summary": "Everything"})
        good_plan = json.dumps(
            {
                "tasks": [
                    {
                        "title": "A",
                        "description": "Do A",
                        "file_paths": ["a.py"],
                        "complexity": "S",
                    },
                    {
                        "title": "B",
                        "description": "Do B",
                        "file_paths": ["b.py"],
                        "complexity": "S",
                    },
                ],
                "summary": "A and B",
            }
        )
        runtime = AsyncMock()
        runtime.execute_step.side_effect = [
            {"content": bad_plan},
            {"content": good_plan},
        ]

        config = {"configurable": {"agent_runtime": runtime}}
        result = await plan_work(state, config)

        assert runtime.execute_step.call_count == 2
        assert result["current_phase"] == "awaiting_spec_approval"
        assert len(result["plan"]["tasks"]) == 2

    async def test_empty_messages_fallback(self, state: dict) -> None:
        state["sanitized_messages"] = []
        good_plan = json.dumps(
            {
                "tasks": [
                    {
                        "title": "A",
                        "description": "Do A",
                        "file_paths": ["a.py"],
                        "complexity": "S",
                    },
                    {
                        "title": "B",
                        "description": "Do B",
                        "file_paths": ["b.py"],
                        "complexity": "S",
                    },
                ],
                "summary": "A and B",
            }
        )
        runtime = AsyncMock()
        runtime.execute_step.return_value = {"content": good_plan}

        config = {"configurable": {"agent_runtime": runtime}}
        await plan_work(state, config)

        call_kwargs = runtime.execute_step.call_args.kwargs
        assert "No description provided" in call_kwargs["messages"][1]["content"]
