"""Tests for ImageRebuildScheduler."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lintel.domain.types import SandboxPoolConfig
from lintel.sandbox_pool_api.scheduler import ImageRebuildScheduler
from lintel.sandbox_pool_api.store import (
    InMemoryImageRebuildStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)


@pytest.fixture()
def config_store() -> InMemorySandboxPoolConfigStore:
    return InMemorySandboxPoolConfigStore()


@pytest.fixture()
def image_store() -> InMemorySandboxImageStore:
    return InMemorySandboxImageStore()


@pytest.fixture()
def rebuild_store() -> InMemoryImageRebuildStore:
    return InMemoryImageRebuildStore()


@pytest.fixture()
def scheduler(
    config_store: InMemorySandboxPoolConfigStore,
    image_store: InMemorySandboxImageStore,
    rebuild_store: InMemoryImageRebuildStore,
) -> ImageRebuildScheduler:
    return ImageRebuildScheduler(
        config_store=config_store,
        image_store=image_store,
        rebuild_store=rebuild_store,
    )


class TestTriggerRebuild:
    async def test_trigger_creates_record_and_image(
        self,
        scheduler: ImageRebuildScheduler,
        rebuild_store: InMemoryImageRebuildStore,
        image_store: InMemorySandboxImageStore,
    ) -> None:
        result = await scheduler.trigger_rebuild(
            "proj-1", trigger="manual", commit_sha="abc123", branch="main"
        )
        assert result["project_id"] == "proj-1"
        assert result["trigger"] == "manual"
        assert result["status"] == "completed"
        assert result["commit_sha"] == "abc123"
        assert result["image_id"]
        assert result["completed_at"] is not None

        images = await image_store.list_all()
        assert len(images) == 1
        assert images[0]["image_id"] == result["image_id"]

    async def test_trigger_defaults(
        self,
        scheduler: ImageRebuildScheduler,
    ) -> None:
        result = await scheduler.trigger_rebuild("proj-2")
        assert result["trigger"] == "manual"
        assert result["branch"] == "main"
        assert result["commit_sha"] == ""


class TestCheckAndRebuild:
    async def test_rebuilds_when_no_previous_rebuild(
        self,
        scheduler: ImageRebuildScheduler,
        config_store: InMemorySandboxPoolConfigStore,
        rebuild_store: InMemoryImageRebuildStore,
    ) -> None:
        await config_store.upsert(
            SandboxPoolConfig(
                config_id=str(uuid4()),
                project_id="proj-new",
                rebuild_interval_seconds=1800,
            )
        )
        await scheduler._check_and_rebuild()

        records = await rebuild_store.list_all(project_id="proj-new")
        assert len(records) == 1
        assert records[0]["trigger"] == "scheduled"

    async def test_skips_when_interval_not_elapsed(
        self,
        scheduler: ImageRebuildScheduler,
        config_store: InMemorySandboxPoolConfigStore,
        rebuild_store: InMemoryImageRebuildStore,
    ) -> None:
        await config_store.upsert(
            SandboxPoolConfig(
                config_id=str(uuid4()),
                project_id="proj-recent",
                rebuild_interval_seconds=1800,
            )
        )
        # Trigger a rebuild first
        await scheduler.trigger_rebuild("proj-recent", trigger="scheduled")

        # Check again — should not trigger another rebuild
        await scheduler._check_and_rebuild()

        records = await rebuild_store.list_all(project_id="proj-recent")
        assert len(records) == 1

    async def test_rebuilds_when_interval_elapsed(
        self,
        scheduler: ImageRebuildScheduler,
        config_store: InMemorySandboxPoolConfigStore,
        rebuild_store: InMemoryImageRebuildStore,
    ) -> None:
        await config_store.upsert(
            SandboxPoolConfig(
                config_id=str(uuid4()),
                project_id="proj-stale",
                rebuild_interval_seconds=60,
            )
        )
        # Manually create an old rebuild record
        from lintel.domain.types import ImageRebuildRecord, ImageRebuildStatus

        old_record = ImageRebuildRecord(
            rebuild_id=str(uuid4()),
            image_id="old-img",
            project_id="proj-stale",
            trigger="scheduled",
            status=ImageRebuildStatus.COMPLETED,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        await rebuild_store.add(old_record)

        await scheduler._check_and_rebuild()

        records = await rebuild_store.list_all(project_id="proj-stale")
        assert len(records) == 2

    async def test_skips_when_interval_is_zero(
        self,
        scheduler: ImageRebuildScheduler,
        config_store: InMemorySandboxPoolConfigStore,
        rebuild_store: InMemoryImageRebuildStore,
    ) -> None:
        await config_store.upsert(
            SandboxPoolConfig(
                config_id=str(uuid4()),
                project_id="proj-disabled",
                rebuild_interval_seconds=0,
            )
        )
        await scheduler._check_and_rebuild()

        records = await rebuild_store.list_all(project_id="proj-disabled")
        assert len(records) == 0


class TestStartStop:
    async def test_start_and_stop(
        self,
        scheduler: ImageRebuildScheduler,
    ) -> None:
        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None

        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._task is None

    async def test_start_is_idempotent(
        self,
        scheduler: ImageRebuildScheduler,
    ) -> None:
        await scheduler.start()
        task1 = scheduler._task
        await scheduler.start()
        assert scheduler._task is task1
        await scheduler.stop()
