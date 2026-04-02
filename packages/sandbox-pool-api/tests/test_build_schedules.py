"""Tests for image build schedule endpoints and scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from lintel.sandbox_pool_api.routes import (
    image_build_schedule_store_provider,
    pooled_sandbox_store_provider,
    router,
    sandbox_image_store_provider,
    sandbox_pool_config_store_provider,
)
from lintel.sandbox_pool_api.scheduler import ImageRebuildScheduler
from lintel.sandbox_pool_api.store import (
    InMemoryImageBuildScheduleStore,
    InMemoryPooledSandboxStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)


@pytest.fixture()
def schedule_store() -> InMemoryImageBuildScheduleStore:
    return InMemoryImageBuildScheduleStore()


@pytest.fixture()
def client(schedule_store: InMemoryImageBuildScheduleStore) -> Generator[TestClient]:
    sandbox_image_store_provider.override(InMemorySandboxImageStore())
    pooled_sandbox_store_provider.override(InMemoryPooledSandboxStore())
    sandbox_pool_config_store_provider.override(InMemorySandboxPoolConfigStore())
    image_build_schedule_store_provider.override(schedule_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    sandbox_image_store_provider.override(None)
    pooled_sandbox_store_provider.override(None)
    sandbox_pool_config_store_provider.override(None)
    image_build_schedule_store_provider.override(None)


class TestBuildScheduleCRUD:
    def test_create_schedule(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-pool/schedules",
            json={
                "schedule_id": "sched-1",
                "repository_url": "https://github.com/org/repo",
                "cron_expression": "*/30 * * * *",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["schedule_id"] == "sched-1"
        assert data["cron_expression"] == "*/30 * * * *"
        assert data["enabled"] is True

    def test_create_duplicate(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"schedule_id": "dup", "repository_url": "https://github.com/a/b"},
        )
        resp = client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"schedule_id": "dup", "repository_url": "https://github.com/a/c"},
        )
        assert resp.status_code == 409

    def test_list_schedules(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"repository_url": "https://github.com/a/b"},
        )
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"repository_url": "https://github.com/a/c"},
        )
        resp = client.get("/api/v1/sandbox-pool/schedules")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_schedule(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"schedule_id": "get-1", "repository_url": "https://github.com/a/b"},
        )
        resp = client.get("/api/v1/sandbox-pool/schedules/get-1")
        assert resp.status_code == 200
        assert resp.json()["schedule_id"] == "get-1"

    def test_get_schedule_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-pool/schedules/missing")
        assert resp.status_code == 404

    def test_update_schedule(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"schedule_id": "upd-1", "repository_url": "https://github.com/a/b"},
        )
        resp = client.patch(
            "/api/v1/sandbox-pool/schedules/upd-1",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/sandbox-pool/schedules/missing",
            json={"enabled": False},
        )
        assert resp.status_code == 404

    def test_delete_schedule(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={"schedule_id": "del-1", "repository_url": "https://github.com/a/b"},
        )
        resp = client.delete("/api/v1/sandbox-pool/schedules/del-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/sandbox-pool/schedules/del-1")
        assert resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/sandbox-pool/schedules/missing")
        assert resp.status_code == 404


class TestTriggerBuild:
    def test_manual_trigger(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={
                "schedule_id": "trig-1",
                "repository_url": "https://github.com/org/repo",
            },
        )
        resp = client.post("/api/v1/sandbox-pool/schedules/trig-1/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["schedule_id"] == "trig-1"
        assert "image" in data
        assert data["image"]["repository_url"] == "https://github.com/org/repo"

    def test_trigger_updates_last_built(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={
                "schedule_id": "trig-2",
                "repository_url": "https://github.com/org/repo",
            },
        )
        client.post("/api/v1/sandbox-pool/schedules/trig-2/trigger")
        resp = client.get("/api/v1/sandbox-pool/schedules/trig-2")
        data = resp.json()
        assert data["last_built_at"] is not None

    def test_trigger_creates_image(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-pool/schedules",
            json={
                "schedule_id": "trig-3",
                "repository_url": "https://github.com/org/repo",
            },
        )
        client.post("/api/v1/sandbox-pool/schedules/trig-3/trigger")
        resp = client.get("/api/v1/sandbox-pool/images")
        images = resp.json()
        assert len(images) == 1
        assert images[0]["repository_url"] == "https://github.com/org/repo"

    def test_trigger_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sandbox-pool/schedules/missing/trigger")
        assert resp.status_code == 404


class TestImageRebuildScheduler:
    async def test_no_enabled_schedules(
        self,
        schedule_store: InMemoryImageBuildScheduleStore,
    ) -> None:
        scheduler = ImageRebuildScheduler(schedule_store)
        due = await scheduler.get_due_schedules()
        assert due == []

    async def test_schedule_is_due(
        self,
        schedule_store: InMemoryImageBuildScheduleStore,
    ) -> None:
        from lintel.domain.types import ImageBuildSchedule

        past = datetime.now(UTC) - timedelta(hours=1)
        sched = ImageBuildSchedule(
            schedule_id="s1",
            repository_url="https://github.com/a/b",
            cron_expression="*/30 * * * *",
            created_at=past,
        )
        await schedule_store.add(sched)
        scheduler = ImageRebuildScheduler(schedule_store)
        due = await scheduler.get_due_schedules()
        assert len(due) == 1
        assert due[0].schedule_id == "s1"

    async def test_recently_built_not_due(
        self,
        schedule_store: InMemoryImageBuildScheduleStore,
    ) -> None:
        from lintel.domain.types import ImageBuildSchedule

        # Use fixed times: now at :15, last built at :10 — both within the same
        # */30 window (:00–:30), so no cron boundary was crossed.
        now = datetime(2026, 1, 1, 12, 15, tzinfo=UTC)
        sched = ImageBuildSchedule(
            schedule_id="s2",
            repository_url="https://github.com/a/b",
            cron_expression="*/30 * * * *",
            last_built_at=datetime(2026, 1, 1, 12, 10, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        )
        await schedule_store.add(sched)
        scheduler = ImageRebuildScheduler(schedule_store)
        due = await scheduler.get_due_schedules(now=now)
        assert due == []

    async def test_mark_built(
        self,
        schedule_store: InMemoryImageBuildScheduleStore,
    ) -> None:
        from lintel.domain.types import ImageBuildSchedule

        sched = ImageBuildSchedule(
            schedule_id="s3",
            repository_url="https://github.com/a/b",
            cron_expression="*/30 * * * *",
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await schedule_store.add(sched)
        scheduler = ImageRebuildScheduler(schedule_store)
        await scheduler.mark_built("s3", commit_sha="abc123")
        item = await schedule_store.get("s3")
        assert item is not None
        assert item["last_commit_sha"] == "abc123"
        assert item["last_built_at"] is not None

    async def test_disabled_schedule_not_due(
        self,
        schedule_store: InMemoryImageBuildScheduleStore,
    ) -> None:
        from lintel.domain.types import ImageBuildSchedule

        sched = ImageBuildSchedule(
            schedule_id="s4",
            repository_url="https://github.com/a/b",
            cron_expression="*/30 * * * *",
            enabled=False,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await schedule_store.add(sched)
        scheduler = ImageRebuildScheduler(schedule_store)
        due = await scheduler.get_due_schedules()
        assert due == []
