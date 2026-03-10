"""Claude Code CLI provider — runs `claude --print` inside a sandbox."""

from __future__ import annotations

import json
import shlex
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.errors import ClaudeCodeCredentialError
from lintel.contracts.types import SandboxJob, TokenStatus

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager

logger = structlog.get_logger()

# Timeout for a full Claude Code invocation (10 minutes)
CLAUDE_CODE_TIMEOUT = 600

# Timeout for the lightweight auth probe
CLAUDE_CODE_PROBE_TIMEOUT = 30


async def validate_claude_token(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
) -> TokenStatus:
    """Validate Claude Code credentials with a lightweight CLI probe."""
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="claude --print --output-format json 'respond with ok' 2>&1 | head -20",
            timeout_seconds=CLAUDE_CODE_PROBE_TIMEOUT,
        ),
    )
    if result.exit_code == 0:
        return TokenStatus.VALID

    combined = result.stdout + result.stderr
    if "authentication_error" in combined or "OAuth token" in combined:
        return TokenStatus.EXPIRED

    if "command not found" in combined or "not found" in combined:
        logger.warning("claude_code_not_installed", output=combined[:200])
        return TokenStatus.INVALID

    logger.warning(
        "claude_code_validation_failed",
        exit_code=result.exit_code,
        output=combined[:300],
    )
    return TokenStatus.INVALID


class ClaudeCodeProvider:
    """Executes agent prompts via `claude` CLI in a sandbox.

    This provider replaces litellm for agent roles that benefit from
    Claude Code's agentic loop (file editing, bash execution, tool use).
    """

    def __init__(self, sandbox_manager: SandboxManager) -> None:
        self._sandbox = sandbox_manager

    async def invoke(
        self,
        prompt: str,
        *,
        sandbox_id: str,
        system_prompt: str = "",
        allowed_tools: list[str] | None = None,
        max_turns: int = 20,
        workdir: str = "/workspace",
        timeout: int = CLAUDE_CODE_TIMEOUT,
    ) -> dict[str, Any]:
        """Execute a prompt via Claude Code CLI and return structured output.

        Returns:
            dict with keys: content, usage, model, exit_code
        Raises:
            ClaudeCodeCredentialError if token is expired/invalid
        """
        # Pre-flight validation
        status = await validate_claude_token(self._sandbox, sandbox_id)
        if status != TokenStatus.VALID:
            raise ClaudeCodeCredentialError(status)

        # Build the claude command
        cmd_parts = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--max-turns",
            str(max_turns),
        ]

        if allowed_tools:
            cmd_parts.extend(["--allowedTools", ",".join(allowed_tools)])

        # Write system prompt to file if provided
        if system_prompt:
            await self._sandbox.write_file(
                sandbox_id, "/tmp/lintel-system-prompt.md", system_prompt
            )
            cmd_parts.extend(["--system-prompt", "/tmp/lintel-system-prompt.md"])

        # Append the user prompt (quoted)
        cmd_parts.append(shlex.quote(prompt))

        full_cmd = " ".join(cmd_parts)
        logger.info(
            "claude_code_invoke",
            sandbox_id=sandbox_id[:12],
            prompt_length=len(prompt),
            max_turns=max_turns,
            allowed_tools=allowed_tools,
        )

        result = await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=full_cmd,
                workdir=workdir,
                timeout_seconds=timeout,
            ),
        )

        if result.exit_code != 0:
            combined = result.stdout + result.stderr
            if "authentication_error" in combined:
                raise ClaudeCodeCredentialError(TokenStatus.EXPIRED)

            logger.warning(
                "claude_code_invoke_failed",
                exit_code=result.exit_code,
                stderr=result.stderr[:500],
            )

        # Parse the JSON output
        parsed = self._parse_output(result.stdout)
        parsed["exit_code"] = result.exit_code
        if result.stderr:
            parsed["stderr"] = result.stderr[:1000]

        logger.info(
            "claude_code_invoke_complete",
            sandbox_id=sandbox_id[:12],
            exit_code=result.exit_code,
            content_length=len(parsed.get("content", "")),
        )

        return parsed

    def _parse_output(self, stdout: str) -> dict[str, Any]:
        """Parse Claude Code JSON output into a standard result dict."""
        if not stdout.strip():
            return {"content": "", "usage": {}, "model": "claude-code"}

        # Claude --output-format json returns a JSON array of content blocks
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # If not valid JSON, treat the raw output as content
            return {"content": stdout, "usage": {}, "model": "claude-code"}

        # Extract text content from the response
        content_parts: list[str] = []
        usage: dict[str, int] = {}

        if isinstance(data, list):
            # Array of content blocks: [{"type": "text", "text": "..."}, ...]
            for block in data:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        content_parts.append(block.get("text", ""))
                    elif block.get("type") == "result":
                        content_parts.append(block.get("result", ""))
        elif isinstance(data, dict):
            # Single response object
            content_parts.append(str(data.get("content", data.get("result", str(data)))))
            if "usage" in data:
                usage = data["usage"]

        return {
            "content": "\n".join(content_parts),
            "usage": usage,
            "model": "claude-code",
        }
