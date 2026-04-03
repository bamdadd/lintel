"""Tests for the zombie run reaper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.pipelines_api._store import InMemoryPipelineStore
from lintel.pipelines_api.reaper import ZombieRunReaper
from lintel.workflows.types import (
    PipelineRun,
    PipelineStatus,
    Stage,
    StageStatus,
)


def _make_run(
    run_id: str = "run-1",
    status: PipelineStatus = PipelineStatus.QUEUED,
    created_at: str = "",
    stages: tuple[Stage, ...] = (),
) -> PipelineRun:
    if not created_at:
        created_at = datetime.now(UTC).isoformat()
    return PipelineRun(
        run_id=run_id,
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="feature_to_pr",
        status=status,
        stages=stages,
        created_at=created_at,
    )


def _old_timestamp(hours: int = 2) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat()


class TestReapStaleQueued:
    async def test_cancels_old_queued_run(self) -> None:
        store = InMemoryPipelineStore()
        run = _make_run(run_id="old-q", status=PipelineStatus.QUEUED, created_at=_old_timestamp(2))
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_queued(max_age_seconds=3600)

        assert count == 1
        updated = await store.get("old-q")
        assert updated is not None
        assert updated.status == PipelineStatus.CANCELLED

    async def test_leaves_recent_queued_run(self) -> None:
        store = InMemoryPipelineStore()
        run = _make_run(run_id="new-q", status=PipelineStatus.QUEUED)
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_queued(max_age_seconds=3600)

        assert count == 0
        updated = await store.get("new-q")
        assert updated is not None
        assert updated.status == PipelineStatus.QUEUED

    async def test_leaves_running_run_untouched(self) -> None:
        store = InMemoryPipelineStore()
        run = _make_run(run_id="r1", status=PipelineStatus.RUNNING, created_at=_old_timestamp(2))
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_queued(max_age_seconds=3600)

        assert count == 0

    async def test_cancels_old_pending_run(self) -> None:
        store = InMemoryPipelineStore()
        run = _make_run(run_id="old-p", status=PipelineStatus.PENDING, created_at=_old_timestamp(2))
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_queued(max_age_seconds=3600)

        assert count == 1
        updated = await store.get("old-p")
        assert updated is not None
        assert updated.status == PipelineStatus.CANCELLED


class TestReapStaleRunning:
    async def test_fails_old_running_run(self) -> None:
        store = InMemoryPipelineStore()
        stages = (
            Stage(
                stage_id="s1",
                name="research",
                stage_type="research",
                status=StageStatus.RUNNING,
            ),
        )
        run = _make_run(
            run_id="old-r",
            status=PipelineStatus.RUNNING,
            created_at=_old_timestamp(3),
            stages=stages,
        )
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_running(max_age_seconds=7200)

        assert count == 1
        updated = await store.get("old-r")
        assert updated is not None
        assert updated.status == PipelineStatus.FAILED

    async def test_marks_running_stages_as_failed(self) -> None:
        store = InMemoryPipelineStore()
        stages = (
            Stage(
                stage_id="s1",
                name="research",
                stage_type="research",
                status=StageStatus.SUCCEEDED,
            ),
            Stage(
                stage_id="s2",
                name="implement",
                stage_type="implement",
                status=StageStatus.RUNNING,
            ),
        )
        run = _make_run(
            run_id="old-r",
            status=PipelineStatus.RUNNING,
            created_at=_old_timestamp(3),
            stages=stages,
        )
        await store.add(run)

        reaper = ZombieRunReaper(store)
        await reaper.reap_stale_running(max_age_seconds=7200)

        updated = await store.get("old-r")
        assert updated is not None
        assert updated.stages[0].status == StageStatus.SUCCEEDED
        assert updated.stages[1].status == StageStatus.FAILED
        assert "zombie reaper" in updated.stages[1].error.lower()

    async def test_leaves_recent_running_run(self) -> None:
        store = InMemoryPipelineStore()
        run = _make_run(run_id="new-r", status=PipelineStatus.RUNNING)
        await store.add(run)

        reaper = ZombieRunReaper(store)
        count = await reaper.reap_stale_running(max_age_seconds=7200)

        assert count == 0


class TestReap:
    async def test_reaps_both_queued_and_running(self) -> None:
        store = InMemoryPipelineStore()
        await store.add(
            _make_run(run_id="q1", status=PipelineStatus.QUEUED, created_at=_old_timestamp(2))
        )
        await store.add(
            _make_run(run_id="r1", status=PipelineStatus.RUNNING, created_at=_old_timestamp(4))
        )
        await store.add(
            _make_run(run_id="ok", status=PipelineStatus.SUCCEEDED, created_at=_old_timestamp(5))
        )

        reaper = ZombieRunReaper(store)
        total = await reaper.reap()

        assert total == 2

    async def test_reap_idempotent(self) -> None:
        store = InMemoryPipelineStore()
        await store.add(
            _make_run(run_id="q1", status=PipelineStatus.QUEUED, created_at=_old_timestamp(2))
        )

        reaper = ZombieRunReaper(store)
        first = await reaper.reap()
        second = await reaper.reap()

        assert first == 1
        assert second == 0

    async def test_skips_terminal_states(self) -> None:
        store = InMemoryPipelineStore()
        for status in [PipelineStatus.SUCCEEDED, PipelineStatus.FAILED, PipelineStatus.CANCELLED]:
            await store.add(
                _make_run(
                    run_id=f"t-{status}",
                    status=status,
                    created_at=_old_timestamp(10),
                )
            )

        reaper = ZombieRunReaper(store)
        total = await reaper.reap()

        assert total == 0
