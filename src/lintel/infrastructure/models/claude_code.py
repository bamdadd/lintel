"""Claude Code CLI provider — runs `claude --print` inside a sandbox."""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.contracts.errors import ClaudeCodeCredentialError
from lintel.contracts.types import SandboxJob, TokenStatus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lintel.contracts.protocols import SandboxManager

logger = structlog.get_logger()


def _is_json(text: str) -> bool:
    """Check if a string is valid JSON."""
    try:
        json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False
    return True


# Timeout for a full Claude Code invocation (15 minutes)
CLAUDE_CODE_TIMEOUT = 900

# Timeout for the lightweight auth probe (just checks CLI + credentials exist)
CLAUDE_CODE_PROBE_TIMEOUT = 10

# How often to poll the output file for new lines (seconds)
STREAM_POLL_INTERVAL = 3


async def validate_claude_token(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
) -> TokenStatus:
    """Validate Claude Code is installed and credentials exist (no API call)."""
    # Check CLI is installed
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="claude --version 2>&1",
            timeout_seconds=CLAUDE_CODE_PROBE_TIMEOUT,
        ),
    )
    combined = result.stdout + result.stderr
    if result.exit_code != 0 or "command not found" in combined or "not found" in combined:
        logger.warning("claude_code_not_installed", output=combined[:200])
        return TokenStatus.INVALID

    # Check credentials file exists (written by _inject_claude_credentials)
    cred_check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "test -f /home/vscode/.claude/.credentials.json"
                " || test -f /home/vscode/.claude/credentials.json"
                " || test -f /home/vscode/.claude.json"
                " || test -f /root/.claude/credentials.json"
            ),
            timeout_seconds=CLAUDE_CODE_PROBE_TIMEOUT,
        ),
    )
    if cred_check.exit_code != 0:
        logger.warning("claude_code_no_credentials", sandbox_id=sandbox_id[:12])
        return TokenStatus.EXPIRED

    return TokenStatus.VALID


def _tool_detail(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Extract a human-readable detail string from a tool_use input."""
    # Description field (Claude Code's own tools use this)
    desc = str(tool_input.get("description", ""))
    if desc:
        return desc
    # Bash/command tools — show the command
    cmd = str(tool_input.get("command", ""))
    if cmd:
        return cmd.split("\n")[0]
    # Read/Write/Edit — show the file path
    fp = str(tool_input.get("file_path", "") or tool_input.get("path", ""))
    if fp:
        return fp
    # Grep/search — show the pattern
    pattern = str(tool_input.get("pattern", ""))
    if pattern:
        return f"/{pattern}/"
    return ""


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

        # Write system prompt to file if provided (unique per invocation to avoid conflicts)
        invocation_id = uuid4().hex[:10]
        if system_prompt:
            prompt_file = f"/tmp/lintel-sysprompt-{invocation_id}.md"
            await self._sandbox.write_file(sandbox_id, prompt_file, system_prompt)
            cmd_parts.extend(["--system-prompt", prompt_file])

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
        # Use unique file names per invocation to avoid conflicts with concurrent runs
        invocation_id = uuid4().hex[:10]
        output_file = f"/tmp/lintel-stream-{invocation_id}.jsonl"
        exit_file = f"/tmp/lintel-exit-{invocation_id}"
        script_file = f"/tmp/lintel-run-{invocation_id}.sh"
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
            prompt_file = f"/tmp/lintel-sysprompt-{invocation_id}.md"
            await self._sandbox.write_file(sandbox_id, prompt_file, system_prompt)
            cmd_parts.extend(["--system-prompt", prompt_file])

        cmd_parts.append(shlex.quote(prompt))

        # Run claude and tee to file so we can tail it
        full_cmd = " ".join(cmd_parts) + f" > {output_file} 2>&1"

        logger.info(
            "claude_code_invoke_streaming",
            sandbox_id=sandbox_id[:12],
            prompt_length=len(prompt),
            max_turns=max_turns,
            invocation_id=invocation_id,
        )

        # Write the command to a script to avoid quoting issues with nohup sh -c
        # Use trap to ensure exit file is written even if the process is killed
        script = (
            f"#!/bin/sh\n"
            f"trap 'echo 130 > {exit_file}' INT TERM HUP\n"
            f"{full_cmd}\n"
            f"echo $? > {exit_file}\n"
        )
        await self._sandbox.write_file(sandbox_id, script_file, script)

        # Start Claude Code in background
        await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=f"chmod +x {script_file} && nohup {script_file} &",
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
        final_content_parts: list[str] = []

        # Number of consecutive polls with no output and no process — detects silent death
        stale_polls = 0
        max_stale_polls = 5  # ~15s with STREAM_POLL_INTERVAL=3

        async def _poll_loop() -> None:
            nonlocal lines_seen, stale_polls
            elapsed = 0
            while elapsed < timeout:
                await asyncio.sleep(STREAM_POLL_INTERVAL)
                elapsed += STREAM_POLL_INTERVAL

                # Check if process finished
                exit_check = await self._sandbox.execute(
                    sandbox_id,
                    SandboxJob(
                        command=f"cat {exit_file} 2>/dev/null || echo running",
                        timeout_seconds=15,
                    ),
                )
                process_done = exit_check.stdout.strip() != "running"

                # Read new lines from the output
                tail_result = await self._sandbox.execute(
                    sandbox_id,
                    SandboxJob(
                        command=f"wc -l < {output_file}",
                        timeout_seconds=15,
                    ),
                )
                try:
                    total_lines = int(tail_result.stdout.strip())
                except ValueError:
                    total_lines = 0

                if total_lines > lines_seen:
                    stale_polls = 0
                    # Read only new lines
                    skip = lines_seen + 1
                    new_lines_result = await self._sandbox.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"sed -n '{skip},{total_lines}p' {output_file}",
                            timeout_seconds=30,
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
                elif not process_done:
                    # No new output and process hasn't finished — check if it's still alive
                    proc_check = await self._sandbox.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"pgrep -f 'lintel-run-{invocation_id}' >/dev/null 2>&1"
                            f" || pgrep -f 'claude.*print' >/dev/null 2>&1"
                            f"; echo $?",
                            timeout_seconds=10,
                        ),
                    )
                    proc_alive = proc_check.stdout.strip() == "0"
                    if not proc_alive:
                        stale_polls += 1
                        if stale_polls >= max_stale_polls:
                            logger.warning(
                                "claude_code_process_dead",
                                sandbox_id=sandbox_id[:12],
                                invocation_id=invocation_id,
                                stale_polls=stale_polls,
                            )
                            break

                if process_done:
                    break

        try:
            await asyncio.wait_for(_poll_loop(), timeout=timeout + 30)
        except TimeoutError:
            logger.warning(
                "claude_code_streaming_hard_timeout",
                sandbox_id=sandbox_id[:12],
                invocation_id=invocation_id,
                timeout=timeout,
            )

        # Read final output for complete parsing
        final_result = await self._sandbox.execute(
            sandbox_id,
            SandboxJob(command=f"cat {output_file}", timeout_seconds=10),
        )
        # Read exit code from the file (may not exist if process died)
        exit_read = await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=f"cat {exit_file} 2>/dev/null || echo 1",
                timeout_seconds=10,
            ),
        )
        exit_code_str = exit_read.stdout.strip()
        try:
            exit_code = int(exit_code_str)
        except ValueError:
            exit_code = 1

        parsed = self._parse_output(final_result.stdout)
        # If _parse_output found nothing, use content collected during streaming
        if not parsed.get("content") and final_content_parts:
            parsed["content"] = "\n".join(p for p in final_content_parts if p)
        parsed["exit_code"] = exit_code

        # Clean up
        await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"rm -f {output_file} {exit_file} {script_file}"
                    f" /tmp/lintel-sysprompt-{invocation_id}.md"
                ),
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
                        detail = _tool_detail(tool_name, tool_input)
                        if detail:
                            return f"🔧 {tool_name}: {detail[:100]}"
                        return f"🔧 {tool_name}"
                    if block.get("type") == "text":
                        text = str(block.get("text", ""))
                        first_line = text.split("\n")[0][:120]
                        if first_line:
                            return first_line
            return ""

        if msg_type == "tool_use":
            tool_name = obj.get("name", "tool")
            tool_input = obj.get("input", {})
            detail = _tool_detail(tool_name, tool_input)
            if detail:
                return f"🔧 {tool_name}: {detail[:100]}"
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
                msg_type = obj.get("type", "")
                # Skip system/init messages — they contain tool lists, not content
                if msg_type == "system":
                    continue
                if msg_type == "result":
                    result_text = str(obj.get("result", ""))
                    if result_text:
                        content_parts.append(result_text)
                    raw_usage = obj.get("usage", {})
                    if raw_usage:
                        usage = {
                            "input_tokens": raw_usage.get("input_tokens", 0),
                            "output_tokens": raw_usage.get("output_tokens", 0),
                        }
                elif msg_type == "assistant":
                    msg = obj.get("message", {})
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            content_parts.append(block.get("text", ""))
            if content_parts:
                return {"content": "\n".join(content_parts), "usage": usage, "model": "claude-code"}
            # Check if stdout is JSONL (every non-empty line parses as JSON) — if so,
            # return empty since we found no content blocks. If it's plain text, return it.
            non_empty = [ln for ln in stdout.strip().split("\n") if ln.strip()]
            all_json = all(_is_json(ln) for ln in non_empty) if non_empty else False
            if all_json:
                return {"content": "", "usage": usage, "model": "claude-code"}
            return {"content": stdout.strip(), "usage": usage, "model": "claude-code"}

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
            # Skip system/init messages
            if data.get("type") == "system":
                return {"content": "", "usage": {}, "model": "claude-code"}
            # Single response object
            content_val = data.get("content", data.get("result", ""))
            if content_val:
                parts.append(str(content_val))
            if "usage" in data:
                usg = data["usage"]

        return {
            "content": "\n".join(parts),
            "usage": usg,
            "model": "claude-code",
        }
