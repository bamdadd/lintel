"""Tests for skipping research/plan nodes when state is rehydrated."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.research import research_codebase


def _make_config(runtime: AsyncMock | None = None) -> dict:
    pipeline_store = AsyncMock()
    pipeline_store.get.return_value = None
    return {
        "configurable": {
            "run_id": "run-1",
            "agent_runtime": runtime,
            "sandbox_manager": None,
            "pipeline_store": pipeline_store,
            "app_state": MagicMock(pipeline_store=pipeline_store),
        },
    }


class TestSkipResearchWhenRehydrated:
    async def test_skips_llm_when_research_context_present(self) -> None:
        """If research_context is already populated (rehydrated), skip the LLM call."""
        mock_runtime = AsyncMock()
        config = _make_config(runtime=mock_runtime)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-1",
            "work_item_id": "wi-1",
            "workspace_path": "/workspace/repo",
            "research_context": "# Rehydrated Research\nPrevious findings.",
        }

        result = await research_codebase(state, config)

        mock_runtime.execute_step.assert_not_awaited()
        assert result["research_context"] == "# Rehydrated Research\nPrevious findings."
        assert result["current_phase"] == "planning"

    async def test_does_not_skip_when_empty(self) -> None:
        """If research_context is empty, proceed normally."""
        mock_runtime = AsyncMock()
        mock_runtime.execute_step.return_value = {
            "content": "new research " * 30,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        config = _make_config(runtime=mock_runtime)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["test"],
            "sandbox_id": None,
            "run_id": "run-1",
            "work_item_id": "wi-1",
            "workspace_path": "/workspace/repo",
            "research_context": "",
        }

        result = await research_codebase(state, config)

        mock_runtime.execute_step.assert_awaited_once()
        assert "new research" in result["research_context"]


class TestSkipPlanWhenRehydrated:
    async def test_skips_llm_when_plan_present(self) -> None:
        """If plan is already populated (rehydrated), skip the LLM call."""
        mock_runtime = AsyncMock()
        config = _make_config(runtime=mock_runtime)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-2",
            "work_item_id": "wi-2",
            "research_context": "research",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {"tasks": [{"title": "Do X"}], "summary": "Do X"},
        }

        result = await plan_work(state, config)

        mock_runtime.execute_step.assert_not_awaited()
        assert result["plan"]["tasks"][0]["title"] == "Do X"
        assert result["current_phase"] == "awaiting_spec_approval"

    async def test_does_not_skip_empty_plan(self) -> None:
        """If plan is empty, proceed normally."""
        mock_runtime = AsyncMock()
        valid_plan = (
            '{"tasks": ['
            '{"title": "Y", "description": "Do Y", "file_paths": ["y.py"], "complexity": "S"}, '
            '{"title": "Z", "description": "Do Z", "file_paths": ["z.py"], "complexity": "S"}'
            '], "summary": "Y and Z"}'
        )
        mock_runtime.execute_step.return_value = {
            "content": valid_plan,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        config = _make_config(runtime=mock_runtime)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["test"],
            "sandbox_id": None,
            "run_id": "run-2",
            "work_item_id": "wi-2",
            "research_context": "",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {},
        }

        result = await plan_work(state, config)

        mock_runtime.execute_step.assert_awaited_once()
        assert result["plan"]["tasks"][0]["title"] == "Y"

    async def test_does_not_skip_plan_without_tasks(self) -> None:
        """Plan with empty tasks list should not be skipped."""
        mock_runtime = AsyncMock()
        valid_plan = (
            '{"tasks": ['
            '{"title": "Z", "description": "Do Z", "file_paths": ["z.py"], "complexity": "S"}, '
            '{"title": "W", "description": "Do W", "file_paths": ["w.py"], "complexity": "S"}'
            '], "summary": "Z and W"}'
        )
        mock_runtime.execute_step.return_value = {
            "content": valid_plan,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        config = _make_config(runtime=mock_runtime)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["test"],
            "sandbox_id": None,
            "run_id": "run-3",
            "work_item_id": "wi-3",
            "research_context": "",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {"tasks": []},
        }

        await plan_work(state, config)

        mock_runtime.execute_step.assert_awaited_once()
