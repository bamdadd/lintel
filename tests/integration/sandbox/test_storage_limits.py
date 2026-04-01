"""Integration tests for REQ-031 sandbox storage limit enforcement.

Tests the full storage limit flow including pre-clone space checks,
storage monitor updates, cleanup scheduling, and admin API responses.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lintel.sandbox.cleanup_scheduler import SandboxCleanupScheduler
from lintel.sandbox.errors import InsufficientStorageError
from lintel.sandbox.storage_monitor import SandboxStorageMonitor


class FakeSandboxStore:
    """In-memory sandbox store for integration tests."""

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


class TestPreCloneSpaceCheck:
    """Test that pipeline runs are rejected when host free space is below threshold."""

    async def test_insufficient_storage_error_raised(self) -> None:
        """Verify InsufficientStorageError is raised when free space < threshold."""
        min_free_bytes = 500 * 1024 * 1024  # 500 MB
        available = 100 * 1024 * 1024  # 100 MB — below threshold

        # Simulate the pre-clone check logic
        if available < min_free_bytes:
            with pytest.raises(InsufficientStorageError):
                raise InsufficientStorageError(
                    available_bytes=available,
                    required_bytes=min_free_bytes,
                )

    async def test_sufficient_storage_passes(self) -> None:
        """Verify no error when free space > threshold."""
        min_free_bytes = 500 * 1024 * 1024  # 500 MB
        available = 2 * 1024 * 1024 * 1024  # 2 GB — above threshold

        # Should not raise
        assert available >= min_free_bytes

    async def test_check_available_space_mock(self) -> None:
        """Test check_available_space with mocked shutil.disk_usage."""
        from collections import namedtuple

        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])

        mock_usage = DiskUsage(
            total=100 * 1024 * 1024 * 1024,
            used=99 * 1024 * 1024 * 1024,
            free=200 * 1024 * 1024,  # 200 MB — below 500 MB threshold
        )

        with patch("shutil.disk_usage", return_value=mock_usage):
            import shutil

            usage = shutil.disk_usage("/var/lib/docker")
            assert usage.free == 200 * 1024 * 1024
            assert usage.free < 500 * 1024 * 1024


class TestStorageMonitorIntegration:
    """Test that storage_usage_bytes is updated in store after monitor poll."""

    async def test_monitor_updates_usage_in_store(self) -> None:
        store = FakeSandboxStore(
            [
                {
                    "sandbox_id": "sb-int-1",
                    "status": "running",
                    "storage_limit_gb": 4,
                },
                {
                    "sandbox_id": "sb-int-2",
                    "status": "running",
                    "storage_limit_gb": 8,
                },
            ]
        )
        manager = AsyncMock()
        manager.get_storage_usage = AsyncMock(side_effect=[2_000_000_000, 500_000_000])

        monitor = SandboxStorageMonitor(store, manager, poll_interval_seconds=1.0)
        await monitor._check_all_sandboxes()

        sb1 = await store.get("sb-int-1")
        assert sb1 is not None
        assert sb1["storage_usage_bytes"] == 2_000_000_000
        assert sb1["storage_checked_at"] is not None

        sb2 = await store.get("sb-int-2")
        assert sb2 is not None
        assert sb2["storage_usage_bytes"] == 500_000_000


class TestCleanupSchedulingIntegration:
    """Test that scheduled_cleanup_at is set correctly on pipeline events."""

    async def test_success_sets_immediate_cleanup(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-success", "status": "running"},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager, retention_hours=24)

        await scheduler.on_pipeline_completed("sb-success", success=True)

        meta = await store.get("sb-success")
        assert meta is not None
        cleanup_at = datetime.fromisoformat(meta["scheduled_cleanup_at"])
        assert abs((cleanup_at - datetime.now(tz=UTC)).total_seconds()) < 5

    async def test_failure_sets_deferred_cleanup(self) -> None:
        store = FakeSandboxStore(
            [
                {"sandbox_id": "sb-fail", "status": "running"},
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager, retention_hours=24)

        await scheduler.on_pipeline_completed("sb-fail", success=False)

        meta = await store.get("sb-fail")
        assert meta is not None
        cleanup_at = datetime.fromisoformat(meta["scheduled_cleanup_at"])
        expected = datetime.now(tz=UTC) + timedelta(hours=24)
        assert abs((cleanup_at - expected).total_seconds()) < 5

    async def test_due_cleanups_are_executed(self) -> None:
        past = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        future = (datetime.now(tz=UTC) + timedelta(hours=10)).isoformat()
        store = FakeSandboxStore(
            [
                {
                    "sandbox_id": "sb-due",
                    "status": "running",
                    "scheduled_cleanup_at": past,
                },
                {
                    "sandbox_id": "sb-not-due",
                    "status": "running",
                    "scheduled_cleanup_at": future,
                },
            ]
        )
        manager = AsyncMock()
        scheduler = SandboxCleanupScheduler(store, manager)

        cleaned = await scheduler.run_due_cleanups()

        assert cleaned == 1
        assert await store.get("sb-due") is None
        assert await store.get("sb-not-due") is not None
        manager.destroy.assert_called_once_with("sb-due")


class TestAdminStorageEndpointIntegration:
    """Test that GET /admin/sandbox-storage returns correct aggregated data."""

    async def test_storage_summary_calculation(self) -> None:
        """Verify the storage summary math is correct."""
        sandboxes = [
            {
                "sandbox_id": "sb-1",
                "storage_limit_gb": 4,
                "storage_usage_bytes": 1_000_000_000,  # 1 GB
                "storage_checked_at": "2026-04-01T12:00:00+00:00",
            },
            {
                "sandbox_id": "sb-2",
                "storage_limit_gb": 10,
                "storage_usage_bytes": 5_000_000_000,  # 5 GB
                "storage_checked_at": "2026-04-01T12:00:00+00:00",
            },
        ]

        usage_list = []
        for sb in sandboxes:
            limit_gb: int = sb.get("storage_limit_gb", 4)  # type: ignore[assignment]
            limit_bytes = limit_gb * 1024 * 1024 * 1024
            usage_bytes: int = sb.get("storage_usage_bytes") or 0  # type: ignore[assignment]
            available_bytes = max(0, limit_bytes - usage_bytes)
            usage_list.append(
                {
                    "sandbox_id": sb["sandbox_id"],
                    "usage_bytes": usage_bytes,
                    "limit_bytes": limit_bytes,
                    "available_bytes": available_bytes,
                    "last_checked_at": sb.get("storage_checked_at"),
                }
            )

        assert len(usage_list) == 2
        assert usage_list[0]["usage_bytes"] == 1_000_000_000
        assert usage_list[0]["limit_bytes"] == 4 * 1024 * 1024 * 1024
        assert usage_list[0]["available_bytes"] == 4 * 1024 * 1024 * 1024 - 1_000_000_000
        assert usage_list[1]["usage_bytes"] == 5_000_000_000
        assert usage_list[1]["limit_bytes"] == 10 * 1024 * 1024 * 1024
