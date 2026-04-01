"""Tests for sandbox storage limits, monitoring, and cleanup (REQ-031)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lintel.sandbox.errors import StorageLimitExceededError
from lintel.sandbox.types import (
    SandboxConfig,
    StorageLimits,
    StorageUsage,
)


class TestStorageLimits:
    def test_default_values(self) -> None:
        limits = StorageLimits()
        assert limits.max_storage_gb == 4
        assert limits.max_allowed_gb == 10
        assert limits.cleanup_threshold_pct == 80

    def test_clamped_to_max_allowed(self) -> None:
        limits = StorageLimits(max_storage_gb=20, max_allowed_gb=10)
        assert limits.max_storage_gb == 10

    def test_custom_values(self) -> None:
        limits = StorageLimits(max_storage_gb=8, max_allowed_gb=10, cleanup_threshold_pct=90)
        assert limits.max_storage_gb == 8
        assert limits.cleanup_threshold_pct == 90

    def test_sandbox_config_has_storage_limits(self) -> None:
        config = SandboxConfig()
        assert config.storage_limits.max_storage_gb == 4

    def test_sandbox_config_custom_storage(self) -> None:
        config = SandboxConfig(storage_limits=StorageLimits(max_storage_gb=6))
        assert config.storage_limits.max_storage_gb == 6


class TestStorageUsage:
    def test_used_mb(self) -> None:
        usage = StorageUsage(used_bytes=500 * 1024 * 1024, limit_bytes=4 * 1024**3)
        assert usage.used_mb == 500

    def test_used_pct(self) -> None:
        limit = 4 * 1024**3  # 4GB
        used = limit // 2  # 50%
        usage = StorageUsage(used_bytes=used, limit_bytes=limit)
        assert abs(usage.used_pct - 50.0) < 0.1

    def test_exceeds_threshold_false(self) -> None:
        usage = StorageUsage(used_bytes=1024, limit_bytes=4 * 1024**3)
        assert not usage.exceeds_threshold

    def test_exceeds_threshold_true(self) -> None:
        limit = 4 * 1024**3
        used = int(limit * 0.85)
        usage = StorageUsage(used_bytes=used, limit_bytes=limit)
        assert usage.exceeds_threshold

    def test_zero_limit_returns_zero_pct(self) -> None:
        usage = StorageUsage(used_bytes=100, limit_bytes=0)
        assert usage.used_pct == 0.0


class TestStorageLimitExceededError:
    def test_message(self) -> None:
        err = StorageLimitExceededError(used_mb=4500, limit_mb=4096)
        assert "4500MB" in str(err)
        assert "4096MB" in str(err)
        assert err.used_mb == 4500
        assert err.limit_mb == 4096


class TestDockerBackendStorageMethods:
    """Tests for DockerSandboxManager storage methods using mocked execute."""

    @pytest.fixture()
    def manager(self) -> AsyncMock:
        """Create a DockerSandboxManager with mocked internals."""
        from lintel.sandbox.docker_backend import DockerSandboxManager

        mgr = DockerSandboxManager()
        # Populate _configs for the sandbox
        config = SandboxConfig(storage_limits=StorageLimits(max_storage_gb=4))
        mgr._configs["test-sandbox"] = config
        return mgr

    async def test_get_storage_usage(self, manager: AsyncMock) -> None:
        from lintel.sandbox.types import SandboxResult

        mock_result = SandboxResult(
            exit_code=0,
            stdout="1073741824\t/workspace\n",  # 1GB
        )
        with patch.object(manager, "execute", new_callable=AsyncMock, return_value=mock_result):
            usage = await manager.get_storage_usage("test-sandbox")
        assert usage.used_bytes == 1073741824
        assert usage.used_mb == 1024
        assert usage.limit_bytes == 4 * 1024**3

    async def test_get_storage_usage_failure(self, manager: AsyncMock) -> None:
        from lintel.sandbox.errors import SandboxExecutionError
        from lintel.sandbox.types import SandboxResult

        mock_result = SandboxResult(exit_code=1, stderr="Permission denied")
        with (
            patch.object(manager, "execute", new_callable=AsyncMock, return_value=mock_result),
            pytest.raises(SandboxExecutionError, match="Failed to check storage"),
        ):
            await manager.get_storage_usage("test-sandbox")

    async def test_cleanup_workspace(self, manager: AsyncMock) -> None:
        from lintel.sandbox.types import SandboxResult

        call_count = 0
        usage_before = StorageUsage(used_bytes=2 * 1024**3, limit_bytes=4 * 1024**3)
        usage_after = StorageUsage(used_bytes=1 * 1024**3, limit_bytes=4 * 1024**3)

        async def mock_get_storage(sid: str) -> StorageUsage:
            nonlocal call_count
            call_count += 1
            return usage_before if call_count == 1 else usage_after

        cleanup_result = SandboxResult(exit_code=0, stdout="")
        with (
            patch.object(manager, "get_storage_usage", side_effect=mock_get_storage),
            patch.object(manager, "execute", new_callable=AsyncMock, return_value=cleanup_result),
        ):
            freed = await manager.cleanup_workspace("test-sandbox")
        assert freed == 1 * 1024**3

    async def test_check_storage_limit_under_threshold(self, manager: AsyncMock) -> None:
        usage = StorageUsage(used_bytes=1 * 1024**3, limit_bytes=4 * 1024**3)
        with patch.object(manager, "get_storage_usage", new_callable=AsyncMock, return_value=usage):
            result = await manager.check_storage_limit("test-sandbox")
        assert result.used_pct < 80.0

    async def test_check_storage_limit_triggers_cleanup(self, manager: AsyncMock) -> None:
        usage_high = StorageUsage(used_bytes=int(3.5 * 1024**3), limit_bytes=4 * 1024**3)
        usage_after = StorageUsage(used_bytes=2 * 1024**3, limit_bytes=4 * 1024**3)

        call_count = 0

        async def mock_get_storage(sid: str) -> StorageUsage:
            nonlocal call_count
            call_count += 1
            return usage_high if call_count == 1 else usage_after

        with (
            patch.object(manager, "get_storage_usage", side_effect=mock_get_storage),
            patch.object(manager, "cleanup_workspace", new_callable=AsyncMock, return_value=0),
        ):
            result = await manager.check_storage_limit("test-sandbox")
        assert result.used_pct == usage_after.used_pct

    async def test_check_storage_limit_raises_when_full(self, manager: AsyncMock) -> None:
        usage_full = StorageUsage(used_bytes=5 * 1024**3, limit_bytes=4 * 1024**3)

        with (
            patch.object(
                manager, "get_storage_usage", new_callable=AsyncMock, return_value=usage_full
            ),
            patch.object(manager, "cleanup_workspace", new_callable=AsyncMock, return_value=0),
            pytest.raises(StorageLimitExceededError),
        ):
            await manager.check_storage_limit("test-sandbox")
