"""Tests for ClaudeCodeProvider.invoke_streaming — the nohup+poll path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lintel.contracts.types import SandboxResult
from lintel.infrastructure.models.claude_code import ClaudeCodeProvider


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


class TestInvokeStreamingHappyPath:
    """Process writes output, exits cleanly."""

    @patch("lintel.infrastructure.models.claude_code.STREAM_POLL_INTERVAL", 0.01)
    async def test_single_poll_success(self) -> None:
        manager = _make_sandbox(
            [
                # Pre-flight: version + creds
                _ok("claude 1.0.0"),
                _ok(),
                # Start nohup
                _ok(),
                # Touch output file
                _ok(),
                # --- Poll iteration 1 ---
                # exit check: process done (exit code written)
                _ok("0"),
                # wc -l: 1 line of output
                _ok("1"),
                # sed: read line 1
                _ok(STREAM_RESULT_LINE),
                # --- After loop ---
                # cat output file
                _ok(STREAM_RESULT_LINE),
                # cat exit file
                _ok("0"),
                # rm cleanup
                _ok(),
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
        # We need enough polls to pass the grace period (startup_grace_polls=10)
        # then max_stale_polls=5 more to detect death.
        # Each poll: exit_check + wc_count (+ pgrep after grace)
        poll_responses: list[SandboxResult] = []

        # Grace period polls (10 polls): exit_check=running, wc=0 each
        for _ in range(10):
            poll_responses.append(_ok("running"))  # exit check
            poll_responses.append(_ok("0"))  # wc -l

        # Post-grace polls (5 polls): exit_check=running, wc=0, pgrep=not found
        for _ in range(5):
            poll_responses.append(_ok("running"))  # exit check
            poll_responses.append(_ok("0"))  # wc -l
            poll_responses.append(_ok("1"))  # pgrep: not found (exit 0, stdout="1")

        manager = _make_sandbox(
            [
                # Pre-flight
                _ok("claude 1.0.0"),
                _ok(),
                # Start nohup
                _ok(),
                # Touch output
                _ok(),
                # Poll iterations
                *poll_responses,
                # After loop: cat output, cat exit, rm
                _ok(""),  # empty output
                _ok("1"),  # exit code 1 (default)
                _ok(),  # cleanup
            ]
        )

        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke_streaming(
            "say hello",
            sandbox_id="sb-1",
            timeout=600,  # large timeout — should bail early via dead detection
        )

        assert result["exit_code"] == 1
        assert result["content"] == ""


class TestInvokeStreamingHardTimeout:
    """asyncio.wait_for fires when poll loop exceeds timeout."""

    @patch("lintel.infrastructure.models.claude_code.STREAM_POLL_INTERVAL", 0.01)
    async def test_hard_timeout_fires(self) -> None:
        """With a tiny timeout, the hard timeout wrapper kicks in."""
        # Create an execute mock that always returns "running" / 0 lines
        manager = AsyncMock()
        manager.write_file = AsyncMock()

        call_count = 0

        async def _execute(*args: object, **kwargs: object) -> SandboxResult:
            nonlocal call_count
            call_count += 1
            # First 2 calls: pre-flight
            if call_count == 1:
                return _ok("claude 1.0.0")
            if call_count == 2:
                return _ok()
            # Next 2: nohup + touch
            if call_count in (3, 4):
                return _ok()
            # All subsequent: poll loop — always "running" with no output
            # Alternate: exit_check returns "running", wc returns "0"
            if call_count % 2 == 1:
                return _ok("running")
            return _ok("0")

        manager.execute = AsyncMock(side_effect=_execute)

        provider = ClaudeCodeProvider(manager)
        # timeout=0.05 seconds — poll loop will be killed by wait_for
        result = await provider.invoke_streaming(
            "say hello",
            sandbox_id="sb-1",
            timeout=0.05,
        )

        # Should complete (not hang) — content may be empty or contain poll artifacts
        assert isinstance(result["content"], str)


class TestInvokeStreamingCredentialFailure:
    """Pre-flight credential check fails."""

    async def test_raises_on_expired_credentials(self) -> None:
        manager = _make_sandbox(
            [
                _ok("claude 1.0.0"),
                _fail(),  # creds not found
            ]
        )
        provider = ClaudeCodeProvider(manager)
        with pytest.raises(Exception, match="(?i)credential|expired"):
            await provider.invoke_streaming("test", sandbox_id="sb-1")
