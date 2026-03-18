"""Tests for the OpenShell sandbox backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lintel.contracts.types import ThreadRef
from lintel.sandbox.errors import SandboxExecutionError, SandboxNotFoundError
from lintel.sandbox.openshell_backend import OpenShellSandboxManager, _run_cli
from lintel.sandbox.types import SandboxConfig, SandboxJob, SandboxResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_process(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ---------------------------------------------------------------------------
# _run_cli
# ---------------------------------------------------------------------------


class TestRunCli:
    async def test_run_cli_success(self) -> None:
        with patch("lintel.sandbox.openshell_backend.asyncio") as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(
                return_value=_mock_process(0, b"ok\n", b"")
            )
            mock_asyncio.wait_for = AsyncMock(return_value=(b"ok\n", b""))
            mock_asyncio.subprocess = __import__("asyncio").subprocess

            # Directly test that _run_cli calls create_subprocess_exec
            proc = _mock_process(0, b"ok\n", b"")
            with patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=proc),
            ):
                exit_code, stdout, _stderr = await _run_cli("sandbox", "list", check=False)
                assert exit_code == 0
                assert stdout == "ok\n"

    async def test_run_cli_failure_raises(self) -> None:
        proc = _mock_process(1, b"", b"error occurred")
        with (
            patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=proc),
            ),
            pytest.raises(SandboxExecutionError, match="error occurred"),
        ):
            await _run_cli("sandbox", "create", check=True)

    async def test_run_cli_failure_no_check(self) -> None:
        proc = _mock_process(1, b"output", b"err")
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            exit_code, _stdout, stderr = await _run_cli("sandbox", "get", "x", check=False)
            assert exit_code == 1
            assert stderr == "err"


# ---------------------------------------------------------------------------
# OpenShellSandboxManager
# ---------------------------------------------------------------------------


class TestOpenShellSandboxManager:
    async def test_create_calls_openshell_sandbox_create(self) -> None:
        manager = OpenShellSandboxManager()
        manager._verified = True

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "", "")),
        ) as mock_cli:
            config = SandboxConfig(image="lintel-sandbox:latest")
            thread_ref = ThreadRef("W1", "C1", "t1")

            sandbox_id = await manager.create(config, thread_ref)

            assert sandbox_id is not None
            assert sandbox_id in manager._sandboxes
            call_args = mock_cli.call_args[0]
            assert call_args[0] == "sandbox"
            assert call_args[1] == "create"
            assert "--name" in call_args

    async def test_create_with_custom_image(self) -> None:
        manager = OpenShellSandboxManager()
        manager._verified = True

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "", "")),
        ) as mock_cli:
            config = SandboxConfig(image="python:3.12")
            thread_ref = ThreadRef("W1", "C1", "t1")

            await manager.create(config, thread_ref)

            call_args = mock_cli.call_args[0]
            assert "--from" in call_args
            idx = list(call_args).index("--from")
            assert call_args[idx + 1] == "python:3.12"

    async def test_execute_returns_sandbox_result(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "hello world\n", "")),
        ):
            job = SandboxJob(command="echo hello world")
            result = await manager.execute("sandbox-1", job)

            assert isinstance(result, SandboxResult)
            assert result.exit_code == 0
            assert "hello world" in result.stdout

    async def test_execute_nonexistent_raises(self) -> None:
        manager = OpenShellSandboxManager()

        with pytest.raises(SandboxNotFoundError):
            await manager.execute("nonexistent", SandboxJob(command="ls"))

    async def test_execute_stream_yields_lines(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "line1\nline2\n", "")),
        ):
            job = SandboxJob(command="ls")
            stream = await manager.execute_stream("sandbox-1", job)

            lines = [line async for line in stream]
            assert "line1" in lines
            assert "line2" in lines
            assert lines[-1] == "__EXIT:0__"

    async def test_read_file(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "file content here", "")),
        ):
            content = await manager.read_file("sandbox-1", "/workspace/test.txt")
            assert content == "file content here"

    async def test_list_files(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "file1.py\nfile2.py\n", "")),
        ):
            files = await manager.list_files("sandbox-1")
            assert files == ["file1.py", "file2.py"]

    async def test_get_status_running(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, '{"status": "running"}', "")),
        ):
            from lintel.sandbox.types import SandboxStatus

            status = await manager.get_status("sandbox-1")
            assert status == SandboxStatus.RUNNING

    async def test_get_status_failed(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(1, "", "not found")),
        ):
            from lintel.sandbox.types import SandboxStatus

            status = await manager.get_status("sandbox-1")
            assert status == SandboxStatus.FAILED

    async def test_destroy_calls_delete(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, "", "")),
        ) as mock_cli:
            await manager.destroy("sandbox-1")

            assert "sandbox-1" not in manager._sandboxes
            call_args = mock_cli.call_args[0]
            assert call_args[0] == "sandbox"
            assert call_args[1] == "delete"
            assert call_args[2] == "lintel-sandbox-1"

    async def test_destroy_nonexistent_is_noop(self) -> None:
        manager = OpenShellSandboxManager()
        await manager.destroy("nonexistent")  # Should not raise

    async def test_reconnect_network_is_noop(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"
        await manager.reconnect_network("sandbox-1")  # Should not raise

    async def test_disconnect_network_is_noop(self) -> None:
        manager = OpenShellSandboxManager()
        manager._sandboxes["sandbox-1"] = "lintel-sandbox-1"
        await manager.disconnect_network("sandbox-1")  # Should not raise

    async def test_ensure_openshell_raises_when_not_found(self) -> None:
        manager = OpenShellSandboxManager()
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(SandboxExecutionError, match="openshell CLI not found"),
        ):
            await manager._ensure_openshell()

    async def test_recover_sandboxes_parses_json(self) -> None:
        manager = OpenShellSandboxManager()

        sandbox_list = [
            {"name": "lintel-abc123", "status": "running", "image": "ubuntu:22.04"},
            {"name": "other-sandbox", "status": "running", "image": "python:3.12"},
        ]

        with patch(
            "lintel.sandbox.openshell_backend._run_cli",
            new=AsyncMock(return_value=(0, __import__("json").dumps(sandbox_list), "")),
        ):
            recovered = await manager.recover_sandboxes()

            # Only the lintel-prefixed sandbox should be recovered
            assert len(recovered) == 1
            assert recovered[0]["sandbox_id"] == "abc123"
            assert recovered[0]["backend"] == "openshell"
            assert "abc123" in manager._sandboxes
