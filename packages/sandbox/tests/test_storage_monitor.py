"""Tests for the SandboxStorageMonitor background task."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.sandbox.storage_monitor import SandboxStorageMonitor


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


class TestSandboxStorageMonitor:
    async def test_check_updates_usage(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running", "storage_limit_gb": 4},
            ]
        )
        manager = AsyncMock()
        manager.get_storage_usage = AsyncMock(return_value=1_000_000)

        monitor = SandboxStorageMonitor(store, manager, poll_interval_seconds=1.0)
        await monitor._check_all_sandboxes()

        updated = await store.get("sb-1")
        assert updated is not None
        assert updated["storage_usage_bytes"] == 1_000_000
        assert updated["storage_checked_at"] is not None

    async def test_skips_destroyed_sandboxes(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "destroyed"},
            ]
        )
        manager = AsyncMock()

        monitor = SandboxStorageMonitor(store, manager)
        await monitor._check_all_sandboxes()

        manager.get_storage_usage.assert_not_called()

    async def test_handles_usage_failure_gracefully(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-1", "status": "running"},
            ]
        )
        manager = AsyncMock()
        manager.get_storage_usage = AsyncMock(side_effect=RuntimeError("container gone"))

        monitor = SandboxStorageMonitor(store, manager)
        await monitor._check_all_sandboxes()

        updated = await store.get("sb-1")
        assert updated is not None
        assert "storage_usage_bytes" not in updated

    async def test_start_stop_lifecycle(self) -> None:
        import asyncio

        store = FakeSandboxStore()
        manager = AsyncMock()

        monitor = SandboxStorageMonitor(store, manager, poll_interval_seconds=0.1)
        await monitor.start()
        assert monitor._task is not None
        await asyncio.sleep(0.05)
        await monitor.stop()
        assert monitor._task is None
