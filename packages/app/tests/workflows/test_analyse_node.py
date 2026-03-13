"""Tests for the analyse workflow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.workflows.nodes.analyse import analyse_code


class TestAnalyseCode:
    async def test_stub_when_no_runtime(self) -> None:
        state: dict[str, Any] = {
            "sanitized_messages": ["refactor the auth module"],
            "thread_ref": "W1/C1/t1",
        }
        config: dict[str, Any] = {"configurable": {}}
        result = await analyse_code(state, config)

        assert result["current_phase"] == "analysing"
        assert len(result["agent_outputs"]) == 1

    async def test_calls_agent_runtime_stream(self) -> None:
        runtime = AsyncMock()
        runtime.execute_step_stream.return_value = {
            "content": "## Summary\nRefactoring needed for auth module.",
        }

        state: dict[str, Any] = {
            "sanitized_messages": ["refactor the auth module"],
            "thread_ref": "W1/C1/t1",
        }
        config: dict[str, Any] = {"configurable": {"agent_runtime": runtime}}
        result = await analyse_code(state, config)

        runtime.execute_step_stream.assert_called_once()
        assert "Refactoring" in result["analysis_context"]
        assert result["current_phase"] == "analysing"

    async def test_uses_research_context(self) -> None:
        runtime = AsyncMock()
        runtime.execute_step_stream.return_value = {
            "content": "Analysis with research context",
        }

        state: dict[str, Any] = {
            "sanitized_messages": ["fix the bug"],
            "thread_ref": "W1/C1/t1",
            "research_context": "Existing research about the codebase",
        }
        config: dict[str, Any] = {"configurable": {"agent_runtime": runtime}}
        await analyse_code(state, config)

        call_kwargs = runtime.execute_step_stream.call_args.kwargs
        assert "Existing research" in call_kwargs["messages"][1]["content"]

    async def test_gathers_sandbox_context(self) -> None:
        runtime = AsyncMock()
        runtime.execute_step_stream.return_value = {"content": "Analysis done"}
        sandbox_mgr = AsyncMock()

        state: dict[str, Any] = {
            "sanitized_messages": ["add feature"],
            "thread_ref": "W1/C1/t1",
            "sandbox_id": "sb-123",
            "workspace_path": "/workspace/repo",
        }
        config: dict[str, Any] = {
            "configurable": {
                "agent_runtime": runtime,
                "sandbox_manager": sandbox_mgr,
            },
        }

        # gather_codebase_context will be called — mock it at module level
        original = None
        try:
            from lintel.workflows.nodes import _codebase_context

            original = _codebase_context.gather_codebase_context
            _codebase_context.gather_codebase_context = AsyncMock(return_value="mock context")
            result = await analyse_code(state, config)
        finally:
            if original is not None:
                _codebase_context.gather_codebase_context = original  # type: ignore[assignment]

        assert result["analysis_context"] == "Analysis done"
        call_kwargs = runtime.execute_step_stream.call_args.kwargs
        assert "mock context" in call_kwargs["messages"][1]["content"]
