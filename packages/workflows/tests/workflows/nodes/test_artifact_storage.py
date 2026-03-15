"""Tests for artifact storage in research and plan nodes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.research import research_codebase


def _make_config(
    *,
    run_id: str = "run-1",
    runtime: AsyncMock | None = None,
    artifact_store: AsyncMock | None = None,
) -> dict:
    pipeline_store = AsyncMock()
    pipeline_store.get.return_value = None
    return {
        "configurable": {
            "run_id": run_id,
            "agent_runtime": runtime,
            "sandbox_manager": None,
            "pipeline_store": pipeline_store,
            "app_state": MagicMock(
                pipeline_store=pipeline_store,
                code_artifact_store=artifact_store,
            ),
            "code_artifact_store": artifact_store,
        },
    }


class TestResearchArtifactStorage:
    async def test_stores_artifact_on_success(self) -> None:
        mock_runtime = AsyncMock()
        mock_runtime.execute_step.return_value = {
            "content": "# Research Report\nFindings here.\n" + "x" * 200,
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        artifact_store = AsyncMock()
        config = _make_config(runtime=mock_runtime, artifact_store=artifact_store)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add a button"],
            "sandbox_id": None,
            "run_id": "run-1",
            "work_item_id": "wi-1",
            "workspace_path": "/workspace/repo",
            "research_context": "",
        }

        result = await research_codebase(state, config)

        assert "# Research Report\nFindings here." in result["research_context"]
        artifact_store.add.assert_awaited_once()
        stored = artifact_store.add.call_args[0][0]
        assert stored.artifact_type == "research_report"
        assert stored.run_id == "run-1"
        assert stored.work_item_id == "wi-1"
        assert "Findings here" in stored.content

    async def test_no_crash_without_artifact_store(self) -> None:
        mock_runtime = AsyncMock()
        mock_runtime.execute_step.return_value = {
            "content": "research report content " * 20,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        config = _make_config(runtime=mock_runtime, artifact_store=None)

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
        assert "research report content" in result["research_context"]


class TestPlanArtifactStorage:
    async def test_stores_plan_artifact_on_success(self) -> None:
        mock_runtime = AsyncMock()
        valid_plan = (
            '{"tasks": ['
            '{"title": "Do X", "description": "X desc", "file_paths": ["x.py"], "complexity": "S"}, '
            '{"title": "Do Y", "description": "Y desc", "file_paths": ["y.py"], "complexity": "S"}'
            '], "summary": "Do X and Y"}'
        )
        mock_runtime.execute_step.return_value = {
            "content": valid_plan,
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        artifact_store = AsyncMock()
        config = _make_config(run_id="run-2", runtime=mock_runtime, artifact_store=artifact_store)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-2",
            "work_item_id": "wi-2",
            "research_context": "some research",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {},
        }

        await plan_work(state, config)

        artifact_store.add.assert_awaited_once()
        stored = artifact_store.add.call_args[0][0]
        assert stored.artifact_type == "plan"
        assert stored.run_id == "run-2"
        assert "Do X" in stored.content

    async def test_no_crash_without_artifact_store(self) -> None:
        mock_runtime = AsyncMock()
        valid_plan = (
            '{"tasks": ['
            '{"title": "Y", "description": "Y desc", "file_paths": ["y.py"], "complexity": "S"}, '
            '{"title": "Z", "description": "Z desc", "file_paths": ["z.py"], "complexity": "S"}'
            '], "summary": "Y and Z"}'
        )
        mock_runtime.execute_step.return_value = {
            "content": valid_plan,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        config = _make_config(runtime=mock_runtime, artifact_store=None)

        state: dict = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["test"],
            "sandbox_id": None,
            "run_id": "run-3",
            "work_item_id": "wi-3",
            "research_context": "",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {},
        }

        result = await plan_work(state, config)
        assert "tasks" in result["plan"]
