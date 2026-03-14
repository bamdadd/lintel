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
                # claude --version check
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                # credentials file check — return valid JSON with future expiry
                SandboxResult(
                    exit_code=0,
                    stdout='{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}',
                    stderr="",
                ),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.VALID

    async def test_expired_token(self) -> None:
        manager = _make_sandbox(
            [
                # claude --version passes
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                # credentials file not found — command echoes MISSING
                SandboxResult(exit_code=0, stdout="MISSING", stderr=""),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.EXPIRED

    async def test_not_installed(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=127, stdout="", stderr="claude: command not found"),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.INVALID

    async def test_unknown_failure(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=1, stdout="", stderr="some random error"),
            ]
        )
        status = await validate_claude_token(manager, "sandbox-1")
        assert status == TokenStatus.INVALID


class TestClaudeCodeProvider:
    async def test_successful_invocation(self) -> None:
        manager = _make_sandbox(
            [
                # validate_claude_token: version check
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                # validate_claude_token: credentials check
                SandboxResult(
                    exit_code=0,
                    stdout='{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}',
                    stderr="",
                ),
                # _write_tmpfs_file: system prompt written via exec (cat heredoc)
                SandboxResult(exit_code=0, stdout="", stderr=""),
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

        # Verify system prompt was written via exec (not write_file — /tmp is tmpfs)
        # The 3rd execute call is the _write_tmpfs_file heredoc for the system prompt
        assert manager.execute.call_count == 4  # version, creds, sysprompt heredoc, claude
        sysprompt_call = manager.execute.call_args_list[2]
        sysprompt_job = sysprompt_call[0][1]  # SandboxJob
        assert "/tmp/lintel-sysprompt-" in sysprompt_job.command

    async def test_expired_token_raises(self) -> None:
        manager = _make_sandbox(
            [
                # validate_claude_token: version check passes
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                # validate_claude_token: credentials not found
                SandboxResult(exit_code=0, stdout="MISSING", stderr=""),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        with pytest.raises(ClaudeCodeCredentialError) as exc_info:
            await provider.invoke("test", sandbox_id="sandbox-1")
        assert exc_info.value.status == TokenStatus.EXPIRED

    async def test_auth_error_during_invocation(self) -> None:
        manager = _make_sandbox(
            [
                # version check
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                # credentials check
                SandboxResult(
                    exit_code=0,
                    stdout='{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}',
                    stderr="",
                ),
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
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                SandboxResult(
                    exit_code=0,
                    stdout='{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}',
                    stderr="",
                ),
                SandboxResult(exit_code=0, stdout="Just plain text response"),
            ]
        )
        provider = ClaudeCodeProvider(manager)
        result = await provider.invoke("test", sandbox_id="sandbox-1")
        assert result["content"] == "Just plain text response"

    async def test_no_system_prompt(self) -> None:
        manager = _make_sandbox(
            [
                SandboxResult(exit_code=0, stdout="claude 1.0.0", stderr=""),
                SandboxResult(
                    exit_code=0,
                    stdout='{"claudeAiOauth":{"expiresAt":"2099-01-01T00:00:00Z"}}',
                    stderr="",
                ),
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
