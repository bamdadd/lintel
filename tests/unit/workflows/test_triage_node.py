"""Tests for the triage workflow node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

from lintel.contracts.workflow_models import AgentStepResult
from lintel.workflows.nodes.triage import _parse_triage, triage_issue


class TestParseTriage:
    def test_parse_json_block(self) -> None:
        content = (
            '```json\n{"type": "bug", "priority": "P1",'
            ' "severity": "high", "summary": "Fix crash"}\n```'
        )
        result = _parse_triage(content)
        assert result.type == "bug"
        assert result.priority == "P1"

    def test_parse_raw_json(self) -> None:
        content = (
            '{"type": "feature", "priority": "P2", "severity": "medium", "summary": "Add widget"}'
        )
        result = _parse_triage(content)
        assert result.type == "feature"

    def test_parse_fallback(self) -> None:
        content = "This is just plain text with no JSON"
        result = _parse_triage(content)
        assert result.type == "feature"
        assert result.priority == "P2"
        assert "plain text" in result.summary


class TestTriageIssue:
    async def test_stub_when_no_runtime(self) -> None:
        state: dict[str, Any] = {
            "sanitized_messages": ["fix the login bug"],
            "thread_ref": "W1/C1/t1",
        }
        config: dict[str, Any] = {"configurable": {}}
        result = await triage_issue(state, config)

        assert result["intent"] == "feature"
        assert result["current_phase"] == "triaging"

    async def test_calls_agent_runtime(self) -> None:
        triage_json = json.dumps(
            {
                "type": "bug",
                "priority": "P1",
                "severity": "high",
                "summary": "Login page crashes on submit",
                "suggested_agents": ["coder"],
            }
        )
        runtime = AsyncMock()
        runtime.execute_step.return_value = AgentStepResult(content=triage_json)

        state: dict[str, Any] = {
            "sanitized_messages": ["fix the login bug"],
            "thread_ref": "W1/C1/t1",
        }
        config: dict[str, Any] = {"configurable": {"agent_runtime": runtime}}
        result = await triage_issue(state, config)

        runtime.execute_step.assert_called_once()
        assert result["intent"] == "bug"

    async def test_empty_messages_fallback(self) -> None:
        runtime = AsyncMock()
        runtime.execute_step.return_value = AgentStepResult(
            content='{"type": "chore", "priority": "P3", "severity": "low", "summary": "cleanup"}'
        )

        state: dict[str, Any] = {
            "sanitized_messages": [],
            "thread_ref": "W1/C1/t1",
        }
        config: dict[str, Any] = {"configurable": {"agent_runtime": runtime}}
        result = await triage_issue(state, config)

        call_kwargs = runtime.execute_step.call_args.kwargs
        assert "No description provided" in call_kwargs["messages"][1]["content"]
        assert result["intent"] == "chore"
