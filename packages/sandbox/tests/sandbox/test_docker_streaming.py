"""Tests for DockerSandboxManager.execute_stream."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lintel.sandbox.docker_backend import DockerSandboxManager
from lintel.sandbox.errors import SandboxTimeoutError
from lintel.sandbox.types import SandboxJob


def _make_manager(container: MagicMock) -> DockerSandboxManager:
    manager = DockerSandboxManager()
    manager._containers["sandbox-1"] = container
    return manager


def _mock_api_stream(chunks: list[tuple[bytes | None, bytes | None]]) -> MagicMock:
    """Build a mock docker low-level API that streams the given (stdout, stderr) chunks."""
    mock_api = MagicMock()
    exec_id = "exec-abc123"
    mock_api.exec_create.return_value = exec_id

    chunk_iter = iter(chunks)

    def _exec_start(*args: object, **kwargs: object) -> object:
        return chunk_iter

    mock_api.exec_start.side_effect = _exec_start
    mock_api.exec_inspect.return_value = {"ExitCode": 0}
    return mock_api


class TestExecuteStreamStdout:
    async def test_stdout_lines_yielded(self) -> None:
        container = MagicMock()
        container.id = "container-abc"
        mock_api = _mock_api_stream([(b"hello\n", None), (b"world\n", None)])
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="echo hello && echo world")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert "hello" in lines
        assert "world" in lines
        assert lines[-1] == "__EXIT:0__"

    async def test_stderr_lines_yielded(self) -> None:
        container = MagicMock()
        container.id = "container-abc"
        mock_api = _mock_api_stream([(None, b"error line\n")])
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="ls /nonexistent")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert "error line" in lines
        assert lines[-1] == "__EXIT:0__"

    async def test_interleaved_stdout_stderr(self) -> None:
        container = MagicMock()
        container.id = "container-abc"
        chunks = [
            (b"stdout line\n", None),
            (None, b"stderr line\n"),
            (b"another stdout\n", None),
        ]
        mock_api = _mock_api_stream(chunks)
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="mixed")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert "stdout line" in lines
        assert "stderr line" in lines
        assert "another stdout" in lines
        assert lines[-1] == "__EXIT:0__"

    async def test_partial_line_buffering(self) -> None:
        """Partial lines without newline are buffered and flushed at end."""
        container = MagicMock()
        container.id = "container-abc"
        # Two chunks that together form one line, no trailing newline
        chunks = [(b"partial", None), (b" line", None)]
        mock_api = _mock_api_stream(chunks)
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="printf 'partial line'")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        # Buffered content flushed at end, before sentinel
        assert "partial line" in lines
        assert lines[-1] == "__EXIT:0__"

    async def test_empty_output_yields_only_sentinel(self) -> None:
        container = MagicMock()
        container.id = "container-abc"
        mock_api = _mock_api_stream([])
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="true")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert lines == ["__EXIT:0__"]

    async def test_empty_lines_are_skipped(self) -> None:
        """Lines that are whitespace-only are not yielded."""
        container = MagicMock()
        container.id = "container-abc"
        chunks = [(b"\n", None), (b"   \n", None), (b"real line\n", None)]
        mock_api = _mock_api_stream(chunks)
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="echo")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert "real line" in lines
        # Empty/whitespace lines not present (other than sentinel)
        assert "" not in lines
        assert "   " not in lines

    async def test_exit_code_in_sentinel(self) -> None:
        container = MagicMock()
        container.id = "container-abc"
        mock_api = _mock_api_stream([(b"output\n", None)])
        mock_api.exec_inspect.return_value = {"ExitCode": 42}
        container.client.api = mock_api

        manager = _make_manager(container)
        job = SandboxJob(command="exit 42")

        lines = []
        async for line in await manager.execute_stream("sandbox-1", job):
            lines.append(line)

        assert lines[-1] == "__EXIT:42__"

    async def test_timeout_raises_sandbox_timeout_error(self) -> None:
        container = MagicMock()
        container.id = "container-abc"

        mock_api = MagicMock()
        mock_api.exec_create.return_value = "exec-id"
        mock_api.exec_start.return_value = iter([])
        container.client.api = mock_api

        manager = _make_manager(container)
        # timeout_seconds=0 so asyncio.wait_for fires immediately on first chunk read
        job = SandboxJob(command="sleep 100", timeout_seconds=0)

        # Patch asyncio.wait_for to simulate a timeout only when called during iteration
        import inspect

        async def _mock_wait_for(coro: object, timeout: object) -> object:
            # Close the coroutine to avoid "never awaited" warning
            if inspect.iscoroutine(coro):
                coro.close()  # type: ignore[union-attr]
            raise TimeoutError("timed out")

        with (
            patch(
                "lintel.sandbox.docker_backend.asyncio.wait_for",
                side_effect=_mock_wait_for,
            ),
            pytest.raises(SandboxTimeoutError),
        ):
            async for _ in await manager.execute_stream("sandbox-1", job):
                pass
