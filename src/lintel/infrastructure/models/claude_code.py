"""Claude Code CLI provider — runs `claude --print` inside a sandbox."""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.errors import ClaudeCodeCredentialError
from lintel.contracts.types import SandboxJob, TokenStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lintel.contracts.protocols import SandboxManager

logger = structlog.get_logger()

# Timeout for a full Claude Code invocation (10 minutes)
CLAUDE_CODE_TIMEOUT = 600

# Timeout for the lightweight auth probe
CLAUDE_CODE_PROBE_TIMEOUT = 30

# How often to poll the output file for new lines (seconds)
STREAM_POLL_INTERVAL = 3


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
            "--permission-mode",
            "bypassPermissions",
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

    async def invoke_streaming(
        self,
        prompt: str,
        *,
        sandbox_id: str,
        system_prompt: str = "",
        allowed_tools: list[str] | None = None,
        max_turns: int = 20,
        workdir: str = "/workspace",
        timeout: int = CLAUDE_CODE_TIMEOUT,
        on_activity: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt via Claude Code CLI with streaming activity updates.

        Uses ``--output-format stream-json`` to capture progress as it happens.
        The ``on_activity`` callback receives human-readable activity lines
        (tool use, file edits, etc.) while Claude Code works.

        Returns the same dict as ``invoke()``.
        """
        # Pre-flight validation
        status = await validate_claude_token(self._sandbox, sandbox_id)
        if status != TokenStatus.VALID:
            raise ClaudeCodeCredentialError(status)

        # Build the claude command with stream-json output to a file
        output_file = "/tmp/lintel-claude-stream.jsonl"
        cmd_parts = [
            "claude",
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--verbose",
            "--output-format",
            "stream-json",
            "--max-turns",
            str(max_turns),
        ]

        if allowed_tools:
            cmd_parts.extend(["--allowedTools", ",".join(allowed_tools)])

        if system_prompt:
            await self._sandbox.write_file(
                sandbox_id, "/tmp/lintel-system-prompt.md", system_prompt
            )
            cmd_parts.extend(["--system-prompt", "/tmp/lintel-system-prompt.md"])

        cmd_parts.append(shlex.quote(prompt))

        # Run claude and tee to file so we can tail it
        full_cmd = " ".join(cmd_parts) + f" > {output_file} 2>&1"

        logger.info(
            "claude_code_invoke_streaming",
            sandbox_id=sandbox_id[:12],
            prompt_length=len(prompt),
            max_turns=max_turns,
        )

        # Write the command to a script to avoid quoting issues with nohup sh -c
        script = f"#!/bin/sh\n{full_cmd}\necho $? > /tmp/lintel-claude-exit\n"
        await self._sandbox.write_file(sandbox_id, "/tmp/lintel-run-claude.sh", script)

        # Start Claude Code in background
        await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command="chmod +x /tmp/lintel-run-claude.sh && nohup /tmp/lintel-run-claude.sh &",
                workdir=workdir,
                timeout_seconds=10,
            ),
        )

        # Ensure output file exists
        await self._sandbox.execute(
            sandbox_id,
            SandboxJob(command=f"touch {output_file}", timeout_seconds=5),
        )

        # Poll the output file for new lines
        lines_seen = 0
        elapsed = 0
        final_content_parts: list[str] = []

        while elapsed < timeout:
            await asyncio.sleep(STREAM_POLL_INTERVAL)
            elapsed += STREAM_POLL_INTERVAL

            # Check if process finished
            exit_check = await self._sandbox.execute(
                sandbox_id,
                SandboxJob(
                    command="cat /tmp/lintel-claude-exit 2>/dev/null || echo running",
                    timeout_seconds=5,
                ),
            )
            process_done = exit_check.stdout.strip() != "running"

            # Read new lines from the output
            tail_result = await self._sandbox.execute(
                sandbox_id,
                SandboxJob(
                    command=f"wc -l < {output_file}",
                    timeout_seconds=5,
                ),
            )
            try:
                total_lines = int(tail_result.stdout.strip())
            except ValueError:
                total_lines = 0

            if total_lines > lines_seen:
                # Read only new lines
                skip = lines_seen + 1
                new_lines_result = await self._sandbox.execute(
                    sandbox_id,
                    SandboxJob(
                        command=f"sed -n '{skip},{total_lines}p' {output_file}",
                        timeout_seconds=10,
                    ),
                )
                for line in new_lines_result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    activity = self._parse_stream_line(line)
                    if activity and on_activity:
                        await on_activity(activity)
                    # Collect text content for final result
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "text":
                            final_content_parts.append(obj.get("text", ""))
                        elif obj.get("type") == "result":
                            final_content_parts.append(obj.get("result", ""))
                    except json.JSONDecodeError:
                        pass
                lines_seen = total_lines

            if process_done:
                break

        # Read final output for complete parsing
        final_result = await self._sandbox.execute(
            sandbox_id,
            SandboxJob(command=f"cat {output_file}", timeout_seconds=10),
        )
        exit_code_str = exit_check.stdout.strip() if process_done else "1"
        try:
            exit_code = int(exit_code_str)
        except ValueError:
            exit_code = 1

        parsed = self._parse_output(final_result.stdout)
        parsed["exit_code"] = exit_code

        # Clean up
        await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=f"rm -f {output_file} /tmp/lintel-claude-exit",
                timeout_seconds=5,
            ),
        )

        logger.info(
            "claude_code_invoke_streaming_complete",
            sandbox_id=sandbox_id[:12],
            exit_code=exit_code,
            content_length=len(parsed.get("content", "")),
            lines_streamed=lines_seen,
        )

        return parsed

    def _parse_stream_line(self, line: str) -> str:
        """Parse a stream-json line into a human-readable activity string."""
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return ""

        msg_type = obj.get("type", "")

        if msg_type == "assistant" and "message" in obj:
            # Assistant message — check content blocks for tool_use
            msg = obj["message"]
            content = msg.get("content", [])
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "tool")
                        tool_input = block.get("input", {})
                        desc = tool_input.get("description", "")
                        if desc:
                            return f"🔧 {tool_name}: {desc[:80]}"
                        return f"🔧 {tool_name}"
                    if block.get("type") == "text":
                        text = str(block.get("text", ""))
                        first_line = text.split("\n")[0][:120]
                        if first_line:
                            return first_line
            return ""

        if msg_type == "tool_use":
            tool_name = obj.get("name", "tool")
            return f"🔧 {tool_name}"

        if msg_type == "tool_result":
            return ""  # Too noisy

        if msg_type == "text":
            text = str(obj.get("text", ""))
            first_line = text.split("\n")[0][:120]
            if first_line:
                return first_line

        if msg_type == "result":
            return "✅ Claude Code finished"

        return ""

    def _parse_output(self, stdout: str) -> dict[str, Any]:
        """Parse Claude Code JSON output into a standard result dict."""
        if not stdout.strip():
            return {"content": "", "usage": {}, "model": "claude-code"}

        # Claude --output-format json returns a JSON array of content blocks.
        # stream-json returns JSONL (one JSON object per line).
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # Try JSONL (stream-json format) — extract text from result/assistant blocks
            content_parts: list[str] = []
            usage: dict[str, int] = {}
            for raw_line in stdout.strip().split("\n"):
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "result":
                    content_parts.append(str(obj.get("result", "")))
                    raw_usage = obj.get("usage", {})
                    if raw_usage:
                        usage = {
                            "input_tokens": raw_usage.get("input_tokens", 0),
                            "output_tokens": raw_usage.get("output_tokens", 0),
                        }
                elif obj.get("type") == "assistant":
                    msg = obj.get("message", {})
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            content_parts.append(block.get("text", ""))
            if content_parts:
                return {"content": "\n".join(content_parts), "usage": usage, "model": "claude-code"}
            return {"content": stdout, "usage": {}, "model": "claude-code"}

        # Extract text content from the response
        parts: list[str] = []
        usg: dict[str, int] = {}

        if isinstance(data, list):
            # Array of content blocks: [{"type": "text", "text": "..."}, ...]
            for block in data:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "result":
                        parts.append(block.get("result", ""))
        elif isinstance(data, dict):
            # Single response object
            parts.append(str(data.get("content", data.get("result", str(data)))))
            if "usage" in data:
                usg = data["usage"]

        return {
            "content": "\n".join(parts),
            "usage": usg,
            "model": "claude-code",
        }
