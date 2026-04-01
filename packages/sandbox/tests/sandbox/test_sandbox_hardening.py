"""Tests for sandbox hardening integration with DockerSandboxManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lintel.contracts.types import ThreadRef
from lintel.sandbox.docker_backend import DockerSandboxManager
from lintel.sandbox.errors import FileWriteLimitExceededError, ToolCallLimitExceededError
from lintel.sandbox.types import (
    NetworkEgressPolicy,
    ResourceLimits,
    SandboxConfig,
    SandboxJob,
    ToolCallLimits,
)


def _make_manager_with_mock() -> tuple[DockerSandboxManager, MagicMock]:
    manager = DockerSandboxManager()
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.create.return_value = mock_container
    manager._client = mock_client
    return manager, mock_client


class TestResourceLimitsApplied:
    async def test_pids_limit_uses_config(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        config = SandboxConfig(resource_limits=ResourceLimits(max_processes=32))
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        kwargs = mock_client.containers.create.call_args[1]
        assert kwargs["pids_limit"] == 32

    async def test_pids_limit_capped_at_256(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        config = SandboxConfig(resource_limits=ResourceLimits(max_processes=512))
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        kwargs = mock_client.containers.create.call_args[1]
        assert kwargs["pids_limit"] == 256

    async def test_storage_opt_set(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        config = SandboxConfig(resource_limits=ResourceLimits(max_disk_mb=2048))
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        kwargs = mock_client.containers.create.call_args[1]
        assert kwargs["storage_opt"] == {"size": "2048m"}

    async def test_custom_seccomp_profile(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        config = SandboxConfig(
            resource_limits=ResourceLimits(seccomp_profile="/etc/seccomp.json")
        )
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        kwargs = mock_client.containers.create.call_args[1]
        assert "seccomp=/etc/seccomp.json" in kwargs["security_opt"]


class TestNetworkEgressControl:
    async def test_egress_script_applied_when_network_enabled(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        mock_container = mock_client.containers.create.return_value
        config = SandboxConfig(
            network_enabled=True,
            network_egress=NetworkEgressPolicy(allowed_domains=("github.com",)),
        )
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        # Should have called exec_run with iptables script (as root)
        calls = mock_container.exec_run.call_args_list
        # First call is chown, second is egress script
        assert len(calls) >= 2
        egress_call = calls[1]
        assert egress_call[1]["user"] == "root"
        script_cmd = egress_call[0][0]
        assert script_cmd[0] == "/bin/sh"

    async def test_no_egress_script_when_no_domains(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        mock_container = mock_client.containers.create.return_value
        config = SandboxConfig(network_enabled=True)
        thread_ref = ThreadRef("W1", "C1", "t1")

        await manager.create(config, thread_ref)

        # Only the chown call, no egress script
        assert mock_container.exec_run.call_count == 1


class TestToolCallLimitsEnforced:
    async def test_execute_tracks_tool_calls(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0, output=(b"ok", b"")
        )
        manager._containers["s1"] = mock_container
        from lintel.sandbox.resource_guard import ResourceGuard

        guard = ResourceGuard(ToolCallLimits(max_tool_calls_per_step=2))
        manager._guards["s1"] = guard

        await manager.execute("s1", SandboxJob(command="echo 1"))
        await manager.execute("s1", SandboxJob(command="echo 2"))

        with pytest.raises(ToolCallLimitExceededError):
            await manager.execute("s1", SandboxJob(command="echo 3"))

    async def test_write_file_tracks_writes(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0, output=(b"", b"")
        )
        manager._containers["s1"] = mock_container
        from lintel.sandbox.resource_guard import ResourceGuard

        guard = ResourceGuard(ToolCallLimits(max_file_writes_per_session=1))
        manager._guards["s1"] = guard

        await manager.write_file("s1", "/workspace/a.py", "x")

        with pytest.raises(FileWriteLimitExceededError):
            await manager.write_file("s1", "/workspace/b.py", "y")


class TestGuardCleanup:
    async def test_destroy_cleans_up_guard(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        manager._containers["s1"] = mock_container
        from lintel.sandbox.resource_guard import ResourceGuard

        manager._guards["s1"] = ResourceGuard(ToolCallLimits())
        manager._configs["s1"] = SandboxConfig()

        await manager.destroy("s1")

        assert "s1" not in manager._guards
        assert "s1" not in manager._configs

    async def test_get_guard_returns_guard(self) -> None:
        manager = DockerSandboxManager()
        from lintel.sandbox.resource_guard import ResourceGuard

        guard = ResourceGuard(ToolCallLimits())
        manager._guards["s1"] = guard
        assert manager.get_guard("s1") is guard

    async def test_get_guard_returns_none_for_unknown(self) -> None:
        manager = DockerSandboxManager()
        assert manager.get_guard("unknown") is None
