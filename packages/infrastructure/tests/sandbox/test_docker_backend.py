"""Tests for the Docker sandbox backend (legacy test file, updated for new API)."""

from __future__ import annotations

from unittest.mock import MagicMock

from lintel.contracts.types import ThreadRef
from lintel.infrastructure.sandbox.docker_backend import DockerSandboxManager
from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult


class TestDockerSandboxManager:
    async def test_create_uses_defense_in_depth_flags(self) -> None:
        manager = DockerSandboxManager()
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.create.return_value = mock_container
        manager._client = mock_client

        config = SandboxConfig(image="lintel-sandbox:latest")
        thread_ref = ThreadRef("W1", "C1", "t1")

        sandbox_id = await manager.create(config, thread_ref)

        assert sandbox_id is not None
        create_kwargs = mock_client.containers.create.call_args
        assert create_kwargs[1]["cap_drop"] == ["ALL"]
        assert create_kwargs[1]["read_only"] is False  # writable for workspace
        assert create_kwargs[1]["network_mode"] == "none"
        assert create_kwargs[1]["security_opt"] == ["no-new-privileges:true"]
        assert create_kwargs[1]["user"] == "vscode"  # non-root for Claude Code
        mock_container.start.assert_called_once()

    async def test_execute_returns_sandbox_result(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=(b"test output", b""),
        )
        manager._containers["sandbox-1"] = mock_container

        job = SandboxJob(command="echo hello")
        result = await manager.execute("sandbox-1", job)

        assert isinstance(result, SandboxResult)
        assert result.exit_code == 0
        assert result.stdout == "test output"

    async def test_destroy_removes_container(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        manager._containers["sandbox-1"] = mock_container

        await manager.destroy("sandbox-1")

        mock_container.remove.assert_called_once_with(force=True)
        assert "sandbox-1" not in manager._containers

    async def test_destroy_nonexistent_is_noop(self) -> None:
        manager = DockerSandboxManager()
        await manager.destroy("nonexistent")  # Should not raise

    async def test_collect_artifacts_returns_diff(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=(b"diff --git a/file.py b/file.py", b""),
        )
        manager._containers["sandbox-1"] = mock_container

        artifacts = await manager.collect_artifacts("sandbox-1")

        assert artifacts["type"] == "diff"
        assert "diff --git" in artifacts["content"]
