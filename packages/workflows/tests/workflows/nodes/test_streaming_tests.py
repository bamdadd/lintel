"""Tests for _stream_execute_with_logging helper."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from lintel.workflows.nodes.implement import _stream_execute_with_logging


class FakeStreamingSandbox:
    """Fake sandbox that streams lines then exits."""

    def __init__(self, lines: list[str], exit_code: int = 0) -> None:
        self._lines = lines
        self._exit_code = exit_code

    async def execute_stream(self, sandbox_id: str, job: object) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            for line in self._lines:
                yield line
            yield f"__EXIT:{self._exit_code}__"

        return _gen()

    async def execute(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError


async def test_collects_output_and_exit_code() -> None:
    sandbox = FakeStreamingSandbox(["line one", "line two", "line three"])
    logged: list[str] = []

    async def log_fn(line: str) -> None:
        logged.append(line)

    output, exit_code = await _stream_execute_with_logging(
        sandbox_manager=sandbox,  # type: ignore[arg-type]
        sandbox_id="sb-1",
        command="pytest",
        workdir="/workspace",
        timeout_seconds=60,
        log_fn=log_fn,
    )

    assert exit_code == 0
    assert output == "line one\nline two\nline three"
    assert logged == ["line one", "line two", "line three"]


async def test_failed_exit_code() -> None:
    sandbox = FakeStreamingSandbox(["FAILED: 2 errors"], exit_code=1)
    logged: list[str] = []

    async def log_fn(line: str) -> None:
        logged.append(line)

    output, exit_code = await _stream_execute_with_logging(
        sandbox_manager=sandbox,  # type: ignore[arg-type]
        sandbox_id="sb-2",
        command="pytest",
        workdir="/workspace",
        timeout_seconds=60,
        log_fn=log_fn,
    )

    assert exit_code == 1
    assert "FAILED" in output
    assert logged == ["FAILED: 2 errors"]


async def test_fallback_to_blocking_execute() -> None:
    fake_result = MagicMock()
    fake_result.stdout = "stdout line\n"
    fake_result.stderr = "stderr line\n"
    fake_result.exit_code = 0

    sandbox = MagicMock()
    sandbox.execute_stream = None
    sandbox.execute = AsyncMock(return_value=fake_result)

    logged: list[str] = []

    async def log_fn(line: str) -> None:
        logged.append(line)

    output, exit_code = await _stream_execute_with_logging(
        sandbox_manager=sandbox,  # type: ignore[arg-type]
        sandbox_id="sb-3",
        command="pytest",
        workdir="/workspace",
        timeout_seconds=60,
        log_fn=log_fn,
    )

    assert exit_code == 0
    assert "stdout line" in output
    assert "stderr line" in output
    assert "stdout line" in logged
    assert "stderr line" in logged
    sandbox.execute.assert_awaited_once()
