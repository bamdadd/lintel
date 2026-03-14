"""Tests for ClaudeCodeProvider.invoke_streaming — the nohup+poll path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from lintel.contracts.types import SandboxResult
from lintel.infrastructure.models.claude_code import ClaudeCodeProvider

VALID_CREDS = '{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}'


def _ok(stdout: str = "", stderr: str = "") -> SandboxResult:
    return SandboxResult(exit_code=0, stdout=stdout, stderr=stderr)


def _fail(stdout: str = "", stderr: str = "") -> SandboxResult:
    return SandboxResult(exit_code=1, stdout=stdout, stderr=stderr)


STREAM_RESULT_LINE = (
    '{"type":"result","subtype":"success","result":"Hello!",'
    '"usage":{"input_tokens":10,"output_tokens":5}}'
)


def _make_sandbox(execute_results: list[SandboxResult]) -> AsyncMock:
    manager = AsyncMock()
    manager.execute = AsyncMock(side_effect=execute_results)
    manager.write_file = AsyncMock()
    return manager


def _preflight() -> list[SandboxResult]:
    """Pre-flight: version check + credentials check."""
    return [_ok("claude 1.0.0"), _ok(VALID_CREDS)]


def _setup_calls() -> list[SandboxResult]:
    """System prompt write + script write + nohup start + touch output."""
    return [_ok(), _ok(), _ok(), _ok()]


class TestInvokeStreamingHappyPath:
    """Process writes output, exits cleanly."""

    @patch("lintel.infrastructure.models.claude_code.STREAM_POLL_INTERVAL", 0.01)
    async def test_single_poll_success(self) -> None:
        manager = _make_sandbox(
            [
                *_preflight(),
                *_setup_calls(),
                # --- Poll iteration 1 ---
                _ok("0"),  # exit check: process done
                _ok("1"),  # wc -l: 1 line
                _ok(STREAM_RESULT_LINE),  # head -5 peek (auth check, first output)
                _ok(STREAM_RESULT_LINE),  # sed: read line 1
                # --- After loop ---
                _ok(STREAM_RESULT_LINE),  # cat output file
                _ok("0"),  # cat exit file
                _ok(),  # rm cleanup
            ]
        )

        provider = ClaudeCodeProvider(manager)
        activities: list[str] = []

        result = await provider.invoke_streaming(
            "say hello",
            sandbox_id="sb-1",
            system_prompt="You are helpful.",
            timeout=10,
            on_activity=AsyncMock(side_effect=lambda a: activities.append(a)),
        )

        assert result["exit_code"] == 0
        assert "Hello!" in result["content"]


class TestInvokeStreamingDeadProcess:
    """Process dies silently — no exit file, no output."""

    @patch("lintel.infrastructure.models.claude_code.STREAM_POLL_INTERVAL", 0.01)
    async def test_detects_dead_process_after_grace(self) -> None:
        """After startup grace, detects no process and bails out."""
        poll_responses: list[SandboxResult] = []

        # Grace period polls (10 polls): exit_check=running, wc=0 each
        for _ in range(10):
            poll_responses.append(_ok("running"))
            poll_responses.append(_ok("0"))

        # Post-grace polls (5 polls): exit_check=running, wc=0, pgrep=not found
        for _ in range(5):
            poll_responses.append(_ok("running"))
            poll_responses.append(_ok("0"))
            poll_responses.append(_ok("1"))  # pgrep: not found

        manager = _make_sandbox(
            [
                *_preflight(),
                *_setup_calls(),
                *poll_responses,
                # After loop: cat output, cat exit, rm
                _ok(""),
                _ok("1"),
                _ok(),
            ]
        )

        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke_streaming(
            "say hello",
            sandbox_id="sb-1",
            timeout=600,
        )

        assert result["exit_code"] == 1
        assert result["content"] == ""


class TestInvokeStreamingHardTimeout:
    """asyncio.wait_for fires when poll loop exceeds timeout."""

    @patch("lintel.infrastructure.models.claude_code.STREAM_POLL_INTERVAL", 0.01)
    async def test_hard_timeout_fires(self) -> None:
        """With a tiny timeout, the hard timeout wrapper kicks in."""
        manager = AsyncMock()
        manager.write_file = AsyncMock()

        call_count = 0

        async def _execute(*args: object, **kwargs: object) -> SandboxResult:
            nonlocal call_count
            call_count += 1
            # Pre-flight (2) + setup (4) = 6 calls
            if call_count == 1:
                return _ok("claude 1.0.0")
            if call_count == 2:
                return _ok(VALID_CREDS)
            if call_count <= 6:
                return _ok()
            # All subsequent: poll loop — always "running" with no output
            if call_count % 2 == 1:
                return _ok("running")
            return _ok("0")

        manager.execute = AsyncMock(side_effect=_execute)

        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke_streaming(
            "say hello",
            sandbox_id="sb-1",
            timeout=0.05,
        )

        assert isinstance(result["content"], str)


class TestInvokeStreamingCredentialFailure:
    """Pre-flight credential check fails."""

    async def test_raises_on_expired_credentials(self) -> None:
        manager = _make_sandbox(
            [
                _ok("claude 1.0.0"),
                _ok("MISSING"),  # creds not found
            ]
        )
        provider = ClaudeCodeProvider(manager)
        with pytest.raises(Exception, match=r"(?i)credential|expired"):
            await provider.invoke_streaming("test", sandbox_id="sb-1")
