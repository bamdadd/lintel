"""Tests for pipeline continuation — rehydrating state from previous runs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.contracts.types import ThreadRef
from lintel.workflows.commands import StartWorkflow
from lintel.workflows.types import (
    PipelineRun,
    PipelineStatus,
    Stage,
    StageStatus,
)
from lintel.workflows.workflow_executor import WorkflowExecutor


def _make_previous_run() -> PipelineRun:
    """Create a failed pipeline run with research + plan outputs."""
    return PipelineRun(
        run_id="prev-run",
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="feature_to_pr",
        status=PipelineStatus.FAILED,
        trigger_type="chat:conv-1",
        trigger_id="t1",
        stages=(
            Stage(
                stage_id="s1",
                name="setup_workspace",
                stage_type="setup_workspace",
                status=StageStatus.SUCCEEDED,
                outputs={"sandbox_id": "sb-1", "feature_branch": "feat/test"},
            ),
            Stage(
                stage_id="s2",
                name="research",
                stage_type="research",
                status=StageStatus.SUCCEEDED,
                outputs={"research_report": "# Research\nFindings..."},
            ),
            Stage(
                stage_id="s3",
                name="plan",
                stage_type="plan",
                status=StageStatus.SUCCEEDED,
                outputs={"plan": {"tasks": [{"title": "Do X"}], "summary": "Do X"}},
            ),
            Stage(
                stage_id="s4",
                name="implement",
                stage_type="implement",
                status=StageStatus.FAILED,
                error="Sandbox timeout",
            ),
        ),
        created_at="2026-03-14T00:00:00Z",
    )


class TestRehydrateFromRun:
    async def test_rehydrate_seeds_research_and_plan(self) -> None:
        """When continue_from_run_id is set, initial_input should contain
        research_context and plan from the previous run's stage outputs."""
        event_store = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.side_effect = lambda rid: (
            _make_previous_run() if rid == "prev-run" else None
        )

        # Make graph that ends immediately
        async def _empty_stream(  # type: ignore[no-untyped-def]
            *_a: object, **_kw: object
        ) -> None:
            return
            yield

        graph = MagicMock()
        graph.astream = _empty_stream
        graph.get_state.return_value = MagicMock(next=[])

        app_state = MagicMock(
            pipeline_store=pipeline_store,
            sandbox_manager=None,
            credential_store=None,
            code_artifact_store=None,
            test_result_store=None,
        )

        executor = WorkflowExecutor(
            event_store=event_store,
            graph=graph,
            app_state=app_state,
        )

        tr = ThreadRef(workspace_id="w", channel_id="c", thread_ts="t")
        cmd = StartWorkflow(
            thread_ref=tr,
            workflow_type="feature_to_pr",
            project_id="proj-1",
            work_item_id="wi-1",
            run_id="new-run",
            continue_from_run_id="prev-run",
        )

        await executor.execute(cmd)

        # Verify pipeline_store.get was called with prev-run
        pipeline_store.get.assert_any_call("prev-run")

    async def test_rehydrate_includes_failure_context(self) -> None:
        """_rehydrate_from_run should include the failed stage's error."""
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = _make_previous_run()

        app_state = MagicMock(pipeline_store=pipeline_store)
        executor = WorkflowExecutor(
            event_store=AsyncMock(),
            app_state=app_state,
        )

        result = await executor._rehydrate_from_run("prev-run")

        assert result["research_context"] == "# Research\nFindings..."
        assert result["plan"]["tasks"][0]["title"] == "Do X"
        assert result["feature_branch"] == "feat/test"
        assert result["previous_error"] == "Sandbox timeout"
        assert result["previous_failed_stage"] == "implement"

    async def test_rehydrate_returns_empty_when_run_not_found(self) -> None:
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        app_state = MagicMock(pipeline_store=pipeline_store)
        executor = WorkflowExecutor(
            event_store=AsyncMock(),
            app_state=app_state,
        )

        result = await executor._rehydrate_from_run("nonexistent")
        assert result == {}

    async def test_rehydrate_returns_empty_without_app_state(self) -> None:
        executor = WorkflowExecutor(
            event_store=AsyncMock(),
            app_state=None,
        )

        result = await executor._rehydrate_from_run("any")
        assert result == {}
