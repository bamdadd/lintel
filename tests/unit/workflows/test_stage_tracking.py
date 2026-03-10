"""Tests for stage tracking: archiving attempts on re-entry."""

from __future__ import annotations

from typing import Any

from lintel.contracts.types import (
    PipelineRun,
    PipelineStatus,
    Stage,
    StageAttempt,
    StageStatus,
)


class FakePipelineStore:
    """In-memory pipeline store for testing stage tracking."""

    def __init__(self, run: PipelineRun) -> None:
        self._runs: dict[str, PipelineRun] = {run.run_id: run}

    async def get(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    async def update(self, run: PipelineRun) -> None:
        self._runs[run.run_id] = run


def _make_run(stages: list[Stage], run_id: str = "run-1") -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="wf-1",
        status=PipelineStatus.RUNNING,
        stages=tuple(stages),
        trigger_type="test",
        trigger_id="t-1",
    )


def _make_config(store: FakePipelineStore, run_id: str = "run-1") -> dict[str, Any]:
    return {"configurable": {"pipeline_store": store, "run_id": run_id}}


class TestStageAttemptDataclass:
    def test_stage_attempt_fields(self) -> None:
        att = StageAttempt(
            attempt=1,
            status=StageStatus.SUCCEEDED,
            inputs={"key": "val"},
            outputs={"result": "ok"},
            duration_ms=500,
            started_at="2026-01-01T00:00:00",
            finished_at="2026-01-01T00:00:01",
            logs=("line1", "line2"),
        )
        assert att.attempt == 1
        assert att.status == StageStatus.SUCCEEDED
        assert att.inputs == {"key": "val"}

    def test_stage_has_attempts_field(self) -> None:
        s = Stage(stage_id="s1", name="test", stage_type="agent")
        assert s.attempts == ()

    def test_stage_with_attempts(self) -> None:
        att = StageAttempt(attempt=1, status=StageStatus.FAILED, error="boom")
        s = Stage(stage_id="s1", name="test", stage_type="agent", attempts=(att,))
        assert len(s.attempts) == 1
        assert s.attempts[0].error == "boom"


class TestArchiveAndReset:
    async def test_first_run_no_archive(self) -> None:
        """First mark_running on a pending stage creates no attempt."""
        from lintel.workflows.nodes._stage_tracking import mark_running

        stage = Stage(stage_id="s1", name="implement", stage_type="agent")
        store = FakePipelineStore(_make_run([stage]))
        config = _make_config(store)

        await mark_running(config, "implement")

        run = await store.get("run-1")
        assert run is not None
        s = run.stages[0]
        assert s.status == StageStatus.RUNNING
        assert len(s.attempts) == 0
        assert s.retry_count == 0

    async def test_reentry_archives_previous(self) -> None:
        """Re-entry on a succeeded stage archives it as attempt 1."""
        from lintel.workflows.nodes._stage_tracking import mark_running

        stage = Stage(
            stage_id="s1",
            name="implement",
            stage_type="agent",
            status=StageStatus.SUCCEEDED,
            outputs={"diff": "old diff"},
            duration_ms=1000,
            started_at="2026-01-01T00:00:00",
            finished_at="2026-01-01T00:00:01",
            logs=("log1",),
        )
        store = FakePipelineStore(_make_run([stage]))
        config = _make_config(store)

        await mark_running(config, "implement", inputs={"review_feedback": "fix X"})

        run = await store.get("run-1")
        assert run is not None
        s = run.stages[0]
        # Current run is fresh
        assert s.status == StageStatus.RUNNING
        assert s.outputs is None
        assert s.logs == ()
        assert s.inputs == {"review_feedback": "fix X"}
        # Previous run archived
        assert len(s.attempts) == 1
        assert s.attempts[0].attempt == 1
        assert s.attempts[0].status == StageStatus.SUCCEEDED
        assert s.attempts[0].outputs == {"diff": "old diff"}
        assert s.attempts[0].logs == ("log1",)
        assert s.retry_count == 1

    async def test_multiple_reentries_accumulate(self) -> None:
        """Multiple re-entries accumulate attempts."""
        from lintel.workflows.nodes._stage_tracking import mark_running

        att1 = StageAttempt(attempt=1, status=StageStatus.SUCCEEDED, outputs={"diff": "v1"})
        stage = Stage(
            stage_id="s1",
            name="implement",
            stage_type="agent",
            status=StageStatus.SUCCEEDED,
            outputs={"diff": "v2"},
            attempts=(att1,),
            retry_count=1,
        )
        store = FakePipelineStore(_make_run([stage]))
        config = _make_config(store)

        await mark_running(config, "implement")

        run = await store.get("run-1")
        assert run is not None
        s = run.stages[0]
        assert len(s.attempts) == 2
        assert s.attempts[0].outputs == {"diff": "v1"}
        assert s.attempts[1].outputs == {"diff": "v2"}
        assert s.retry_count == 2

    async def test_update_stage_preserves_attempts(self) -> None:
        """update_stage should not lose attempt history."""
        from lintel.workflows.nodes._stage_tracking import update_stage

        att1 = StageAttempt(attempt=1, status=StageStatus.FAILED, error="old")
        stage = Stage(
            stage_id="s1",
            name="implement",
            stage_type="agent",
            status=StageStatus.RUNNING,
            attempts=(att1,),
            retry_count=1,
        )
        store = FakePipelineStore(_make_run([stage]))
        config = _make_config(store)

        await update_stage(config, "run-1", "implement", "succeeded", outputs={"diff": "new"})

        run = await store.get("run-1")
        assert run is not None
        s = run.stages[0]
        assert s.status == StageStatus.SUCCEEDED
        assert s.outputs == {"diff": "new"}
        assert len(s.attempts) == 1
        assert s.attempts[0].error == "old"

    async def test_append_log_preserves_attempts(self) -> None:
        """append_log should not lose attempt history."""
        from lintel.workflows.nodes._stage_tracking import append_log

        att1 = StageAttempt(attempt=1, status=StageStatus.FAILED)
        stage = Stage(
            stage_id="s1",
            name="implement",
            stage_type="agent",
            status=StageStatus.RUNNING,
            attempts=(att1,),
        )
        store = FakePipelineStore(_make_run([stage]))
        config = _make_config(store)

        await append_log(config, "implement", "new log line")

        run = await store.get("run-1")
        assert run is not None
        s = run.stages[0]
        assert "new log line" in s.logs
        assert len(s.attempts) == 1
