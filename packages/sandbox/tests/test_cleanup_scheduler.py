"""Tests for the SandboxCleanupScheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

from lintel.sandbox.cleanup_scheduler import SandboxCleanupScheduler


class FakeSandboxStore:
    """In-memory sandbox store for testing."""

    def __init__(self, sandboxes: list[dict[str, Any]] | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        for sb in sandboxes or []:
            self._data[sb["sandbox_id"]] = dict(sb)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._data.get(sandbox_id)

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._data[sandbox_id] = metadata

    async def remove(self, sandbox_id: str) -> None:
        self._data.pop(sandbox_id, None)


class TestSandboxCleanupScheduler:
    async def test_success_schedules_immediate_cleanup(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running"},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager, retention_hours=24)

        await scheduler.on_pipeline_completed("sb-1", success=True)

        meta = await store.get("sb-1")
        assert meta is not None
        cleanup_at = datetime.fromisoformat(meta["scheduled_cleanup_at"])
        # Should be approximately now (within 5 seconds)
        assert abs((cleanup_at - datetime.now(tz=UTC)).total_seconds()) < 5

    async def test_failure_schedules_deferred_cleanup(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running"},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager, retention_hours=24)

        await scheduler.on_pipeline_completed("sb-1", success=False)

        meta = await store.get("sb-1")
        assert meta is not None
        cleanup_at = datetime.fromisoformat(meta["scheduled_cleanup_at"])
        expected = datetime.now(tz=UTC) + timedelta(hours=24)
        # Should be approximately 24 hours from now (within 5 seconds)
        assert abs((cleanup_at - expected).total_seconds()) < 5

    async def test_run_due_cleanups_destroys_past_due(self) -> None:
        past = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running", "scheduled_cleanup_at": past},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager)

        cleaned = await scheduler.run_due_cleanups()

        assert cleaned == 1
        manager.destroy.assert_called_once_with("sb-1")
        assert await store.get("sb-1") is None

    async def test_run_due_cleanups_skips_future(self) -> None:
        future = (datetime.now(tz=UTC) + timedelta(hours=10)).isoformat()
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running", "scheduled_cleanup_at": future},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager)

        cleaned = await scheduler.run_due_cleanups()

        assert cleaned == 0
        manager.destroy.assert_not_called()
        assert await store.get("sb-1") is not None

    async def test_missing_sandbox_logs_warning(self) -> None:
        store = FakeSandboxStore()
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager)

        # Should not raise
        await scheduler.on_pipeline_completed("nonexistent", success=True)
