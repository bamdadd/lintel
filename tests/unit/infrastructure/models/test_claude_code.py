"""Tests for the Claude Code CLI provider."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lintel.contracts.errors import ClaudeCodeCredentialError
from lintel.contracts.types import SandboxResult, TokenStatus
from lintel.infrastructure.models.claude_code import (
    ClaudeCodeProvider,
    validate_claude_token,
)


def _make_sandbox(execute_results: list[SandboxResult]) -> AsyncMock:
    """Create a mock SandboxManager with queued execute results."""
    manager = AsyncMock()
    manager.execute = AsyncMock(side_effect=execute_results)
    manager.write_file = AsyncMock()
    return manager


class TestValidateClaudeToken:
    async def test_valid_token(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=0, stdout='[{"type":"text","text":"ok"}]'),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.VALID

    async def test_expired_token(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=1, stderr="authentication_error: OAuth token expired"),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.EXPIRED

    async def test_not_installed(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=127, stderr="claude: command not found"),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.INVALID

    async def test_unknown_failure(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=1, stderr="some random error"),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.INVALID


class TestClaudeCodeProvider:
    async def test_successful_invocation(self) -> None:
        manager = _make_sandbox(
            [
                # validate_claude_token probe
                SandboxResult(exit_code=0, stdout="ok"),
                # actual claude --print invocation
                SandboxResult(
                    exit_code=0,
                    stdout='[{"type":"text","text":"Implementation complete."}]',
                ),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke(
            "implement the feature",
            sandbox_id="sandbox-1",
            system_prompt="You are a coder.",
        )
        assert result["content"] == "Implementation complete."
        assert result["exit_code"] == 0
        assert result["model"] == "claude-code"

        # Verify system prompt was written to file
        manager.write_file.assert_called_once()
        call_args = manager.write_file.call_args
        assert call_args[0][1].startswith("/tmp/lintel-sysprompt-")

    async def test_expired_token_raises(self) -> None:
        manager = _make_sandbox(
            [
                # validate_claude_token probe fails
                SandboxResult(exit_code=1, stderr="authentication_error"),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        with pytest.raises(ClaudeCodeCredentialError) as exc_info:
            await provider.invoke("test", sandbox_id="sandbox-1")
        assert exc_info.value.status == TokenStatus.EXPIRED

    async def test_auth_error_during_invocation(self) -> None:
        manager = _make_sandbox(
            [
                # probe passes
                SandboxResult(exit_code=0, stdout="ok"),
                # invocation fails with auth error
                SandboxResult(exit_code=1, stderr="authentication_error: token expired"),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        with pytest.raises(ClaudeCodeCredentialError):
            await provider.invoke("test", sandbox_id="sandbox-1")

    async def test_parse_plain_text_output(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=0, stdout="ok"),
                SandboxResult(exit_code=0, stdout="Just plain text response"),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke("test", sandbox_id="sandbox-1")
        assert result["content"] == "Just plain text response"

    async def test_no_system_prompt(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=0, stdout="ok"),
                SandboxResult(exit_code=0, stdout='[{"type":"text","text":"done"}]'),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke("test", sandbox_id="sandbox-1")
        # write_file should NOT be called (no system prompt)
        manager.write_file.assert_not_called()
        assert result["content"] == "done"


class TestClaudeCodeCredentialError:
    def test_expired_message(self) -> None:
        err = ClaudeCodeCredentialError(TokenStatus.EXPIRED, "user-1")
        assert "expired" in str(err).lower()
        assert err.status == TokenStatus.EXPIRED
        assert err.user_id == "user-1"

    def test_not_configured_message(self) -> None:
        err = ClaudeCodeCredentialError(TokenStatus.NOT_CONFIGURED)
        assert "no credentials are configured" in str(err).lower()

    def test_invalid_message(self) -> None:
        err = ClaudeCodeCredentialError(TokenStatus.INVALID)
        assert "invalid" in str(err).lower()
