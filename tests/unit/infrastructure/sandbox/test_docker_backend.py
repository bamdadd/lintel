"""Tests for DockerSandboxManager with mocked Docker client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lintel.contracts.errors import (
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
)
from lintel.contracts.types import SandboxConfig, SandboxJob, SandboxStatus, ThreadRef
from lintel.infrastructure.sandbox.docker_backend import DockerSandboxManager


def _make_thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")


def _make_exec_result(
    exit_code: int = 0,
    stdout: bytes = b"ok\n",
    stderr: bytes = b"",
) -> MagicMock:
    result = MagicMock()
    result.exit_code = exit_code
    result.output = (stdout, stderr)
    return result


class TestCreate:
    async def test_returns_sandbox_id(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.containers.create.return_value = container
        manager._client = client

        sandbox_id = await manager.create(SandboxConfig(), _make_thread_ref())

        assert isinstance(sandbox_id, str)
        assert len(sandbox_id) == 36  # UUID
        client.containers.create.assert_called_once()
        container.start.assert_called_once()

    async def test_network_mode_none_by_default(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.containers.create.return_value = container
        manager._client = client

        await manager.create(SandboxConfig(), _make_thread_ref())

        call_kwargs = client.containers.create.call_args[1]
        assert call_kwargs["network_mode"] == "none"

    async def test_network_mode_bridge_when_enabled(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.containers.create.return_value = container
        manager._client = client

        await manager.create(SandboxConfig(network_enabled=True), _make_thread_ref())

        call_kwargs = client.containers.create.call_args[1]
        assert call_kwargs["network_mode"] == "bridge"

    async def test_pulls_image_when_not_found_locally(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.images.get.side_effect = Exception("not found")
        client.containers.create.return_value = container
        manager._client = client

        await manager.create(SandboxConfig(), _make_thread_ref())

        client.images.pull.assert_called_once_with(SandboxConfig().image)
        client.containers.create.assert_called_once()

    async def test_skips_pull_when_image_exists(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.containers.create.return_value = container
        manager._client = client

        await manager.create(SandboxConfig(), _make_thread_ref())

        client.images.pull.assert_not_called()

    async def test_environment_passed(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        client = MagicMock()
        client.containers.create.return_value = container
        manager._client = client

        env = frozenset([("CI", "true"), ("FOO", "bar")])
        await manager.create(SandboxConfig(environment=env), _make_thread_ref())

        call_kwargs = client.containers.create.call_args[1]
        assert call_kwargs["environment"] == {"CI": "true", "FOO": "bar"}


class TestExecute:
    async def test_returns_sandbox_result(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(0, b"hello\n", b"")
        manager._containers["s1"] = container

        result = await manager.execute("s1", SandboxJob(command="echo hello"))

        assert result.exit_code == 0
        assert result.stdout == "hello\n"
        assert result.stderr == ""

    async def test_demux_separates_stderr(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(1, b"out", b"err")
        manager._containers["s1"] = container

        result = await manager.execute("s1", SandboxJob(command="fail"))

        assert result.stdout == "out"
        assert result.stderr == "err"

    async def test_not_found_raises(self) -> None:
        manager = DockerSandboxManager()
        with pytest.raises(SandboxNotFoundError):
            await manager.execute("nonexistent", SandboxJob(command="x"))

    async def test_timeout_raises(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()

        async def slow_exec(*_args: object, **_kwargs: object) -> None:
            import asyncio

            await asyncio.sleep(10)

        manager._containers["s1"] = container

        with patch("asyncio.to_thread", side_effect=slow_exec), pytest.raises(SandboxTimeoutError):
            await manager.execute("s1", SandboxJob(command="sleep 999", timeout_seconds=0))


class TestReadFile:
    async def test_reads_via_cat(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(0, b"file content", b"")
        manager._containers["s1"] = container

        content = await manager.read_file("s1", "/workspace/f.txt")
        assert content == "file content"

    async def test_error_raises(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(1, b"", b"No such file")
        manager._containers["s1"] = container

        with pytest.raises(SandboxExecutionError):
            await manager.read_file("s1", "/workspace/f.txt")

    async def test_not_found_raises(self) -> None:
        manager = DockerSandboxManager()
        with pytest.raises(SandboxNotFoundError):
            await manager.read_file("nope", "/f.txt")


class TestWriteFile:
    async def test_writes_via_base64(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(0, b"", b"")
        manager._containers["s1"] = container

        await manager.write_file("s1", "/workspace/f.txt", "content")

        # Should have been called twice: mkdir -p and base64 write
        assert container.exec_run.call_count == 2

    async def test_not_found_raises(self) -> None:
        manager = DockerSandboxManager()
        with pytest.raises(SandboxNotFoundError):
            await manager.write_file("nope", "/f.txt", "x")


class TestListFiles:
    async def test_parses_ls_output(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(0, b"a.py\nb.py\nc.py\n", b"")
        manager._containers["s1"] = container

        files = await manager.list_files("s1")
        assert files == ["a.py", "b.py", "c.py"]

    async def test_error_raises(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(2, b"", b"not found")
        manager._containers["s1"] = container

        with pytest.raises(SandboxExecutionError):
            await manager.list_files("s1", "/nonexistent")


class TestGetStatus:
    async def test_running(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.status = "running"
        manager._containers["s1"] = container

        status = await manager.get_status("s1")
        assert status == SandboxStatus.RUNNING

    async def test_exited(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.status = "exited"
        manager._containers["s1"] = container

        status = await manager.get_status("s1")
        assert status == SandboxStatus.COMPLETED

    async def test_unknown_defaults_to_failed(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.status = "unknown_state"
        manager._containers["s1"] = container

        status = await manager.get_status("s1")
        assert status == SandboxStatus.FAILED


class TestDestroy:
    async def test_removes_container(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        manager._containers["s1"] = container

        await manager.destroy("s1")

        container.remove.assert_called_once_with(force=True)
        assert "s1" not in manager._containers

    async def test_noop_for_unknown_id(self) -> None:
        manager = DockerSandboxManager()
        await manager.destroy("nonexistent")  # should not raise


class TestCollectArtifacts:
    async def test_returns_diff(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.exec_run.return_value = _make_exec_result(0, b"diff output", b"")
        manager._containers["s1"] = container

        result = await manager.collect_artifacts("s1")
        assert result["type"] == "diff"
        assert result["content"] == "diff output"


class TestRecoverContainers:
    async def test_recovers_running_containers(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.labels = {"lintel.sandbox_id": "orphan-1"}
        container.status = "running"
        client = MagicMock()
        client.containers.list.return_value = [container]
        manager._client = client

        recovered = await manager.recover_containers()

        assert recovered == ["orphan-1"]
        assert manager._containers["orphan-1"] is container
        container.remove.assert_not_called()

    async def test_destroys_exited_containers(self) -> None:
        manager = DockerSandboxManager()
        container = MagicMock()
        container.labels = {"lintel.sandbox_id": "dead-1"}
        container.status = "exited"
        client = MagicMock()
        client.containers.list.return_value = [container]
        manager._client = client

        recovered = await manager.recover_containers()

        assert recovered == []
        container.remove.assert_called_once_with(force=True)

    async def test_skips_known_containers(self) -> None:
        manager = DockerSandboxManager()
        known = MagicMock()
        known.labels = {"lintel.sandbox_id": "known-1"}
        known.status = "running"
        manager._containers["known-1"] = known
        client = MagicMock()
        client.containers.list.return_value = [known]
        manager._client = client

        recovered = await manager.recover_containers()

        assert recovered == []
