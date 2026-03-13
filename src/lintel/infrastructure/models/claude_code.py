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


def _read_host_credentials() -> str | None:
    """Read Claude Code credentials from the host system (macOS Keychain or Linux filesystem).

    Returns the raw JSON string or None if unavailable.
    """
    import platform
    import subprocess

    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            logger.debug("claude_code_keychain_read_failed")
        return None

    # Linux: read from filesystem
    from pathlib import Path

    for cred_path in [
        Path.home() / ".claude" / ".credentials.json",
        Path.home() / ".claude" / "credentials.json",
    ]:
        if cred_path.is_file():
            try:
                return cred_path.read_text().strip()
            except Exception:
                logger.debug("claude_code_creds_file_read_failed", path=str(cred_path))
    return None


def _validate_credentials_json(creds_json: str) -> bool:
    """Check if credentials JSON contains a non-expired token. Returns True if valid."""
    import json as _json
    from datetime import UTC, datetime

    try:
        creds = _json.loads(creds_json)
    except (json.JSONDecodeError, ValueError):
        return False

    expires_at = creds.get("claudeAiOauth", {}).get("expiresAt")
    if expires_at:
        if isinstance(expires_at, str):
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            exp_dt = datetime.fromtimestamp(expires_at / 1000, tz=UTC)
        if datetime.now(tz=UTC) >= exp_dt:
            return False
    return True


async def _inject_credentials_into_sandbox(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    creds_json: str,
) -> bool:
    """Write credentials JSON into a sandbox. Returns True on success."""
    try:
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command="mkdir -p /home/vscode/.claude", timeout_seconds=5),
        )
        await sandbox_manager.write_file(
            sandbox_id,
            "/home/vscode/.claude/.credentials.json",
            creds_json,
        )
        return True
    except Exception:
        logger.debug("claude_code_inject_creds_failed", sandbox_id=sandbox_id[:12])
        return False


async def refresh_credentials_for_sandbox(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
) -> bool:
    """Read fresh credentials from the host and inject into a single sandbox.

    Works on both macOS (Keychain) and Linux (filesystem).
    Returns True if successfully refreshed.
    """
    creds_json = _read_host_credentials()
    if not creds_json:
        logger.debug("claude_code_no_host_credentials", sandbox_id=sandbox_id[:12])
        return False

    if not _validate_credentials_json(creds_json):
        logger.warning("claude_code_host_token_expired", sandbox_id=sandbox_id[:12])
        return False

    return await _inject_credentials_into_sandbox(sandbox_manager, sandbox_id, creds_json)


async def _refresh_token_from_keychain(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
) -> bool:
    """Pull fresh Claude Code credentials from host and write to sandbox.

    Returns True if successfully refreshed.
    """
    return await refresh_credentials_for_sandbox(sandbox_manager, sandbox_id)


async def _write_tmpfs_file(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    path: str,
    content: str,
) -> None:
    """Write a file into a sandbox using exec (not put_archive).

    Docker's put_archive API silently fails on tmpfs-mounted paths like /tmp.
    This uses a heredoc via exec to write files correctly to any filesystem.
    """
    # Use a unique delimiter unlikely to appear in content
    delimiter = f"LINTEL_EOF_{uuid4().hex[:8]}"
    await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"cat > {path} << '{delimiter}'\n{content}\n{delimiter}",
            timeout_seconds=10,
        ),
    )


async def validate_claude_token(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
) -> TokenStatus:
    """Validate Claude Code is installed and credentials exist (no API call)."""
    logger.info("claude_code_validate_start", sandbox_id=sandbox_id[:12])
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

    # Check credentials file exists and token hasn't expired
    cred_check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "cat /home/vscode/.claude/.credentials.json"
                " 2>/dev/null || cat /home/vscode/.claude/credentials.json"
                " 2>/dev/null || echo MISSING"
            ),
            timeout_seconds=CLAUDE_CODE_PROBE_TIMEOUT,
        ),
    )
    cred_output = cred_check.stdout.strip()
    if cred_output == "MISSING" or not cred_output:
        logger.warning("claude_code_no_credentials", sandbox_id=sandbox_id[:12])
        return TokenStatus.EXPIRED

    # Parse credentials and check expiresAt
    try:
        import json as _json
        from datetime import UTC, datetime

        creds = _json.loads(cred_output)
        oauth = creds.get("claudeAiOauth", {})
        expires_at = oauth.get("expiresAt")
        if expires_at:
            # expiresAt is an ISO timestamp or Unix epoch ms
            if isinstance(expires_at, str):
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp_dt = datetime.fromtimestamp(expires_at / 1000, tz=UTC)
            now = datetime.now(tz=UTC)
            if now >= exp_dt:
                logger.warning(
                    "claude_code_token_expired",
                    sandbox_id=sandbox_id[:12],
                    expires_at=str(exp_dt),
                    now=str(now),
                )
                # Try to re-inject fresh credentials from host Keychain
                refreshed = await _refresh_token_from_keychain(
                    sandbox_manager, sandbox_id,
                )
                if refreshed:
                    logger.info(
                        "claude_code_token_refreshed",
                        sandbox_id=sandbox_id[:12],
                    )
                    return TokenStatus.VALID
                return TokenStatus.EXPIRED
            logger.info(
                "claude_code_token_valid",
                sandbox_id=sandbox_id[:12],
                expires_in_minutes=int((exp_dt - now).total_seconds() / 60),
            )
    except Exception:
        # Can't parse — assume valid and let the actual call fail with a clear error
        logger.debug("claude_code_creds_parse_failed", sandbox_id=sandbox_id[:12])

    logger.info("claude_code_validate_ok", sandbox_id=sandbox_id[:12])
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
            await _write_tmpfs_file(self._sandbox, sandbox_id, prompt_file, system_prompt)
            cmd_parts.extend(["--system-prompt", prompt_file])

        # Append the user prompt (quoted)
        cmd_parts.append(shlex.quote(prompt))

        full_cmd = " ".join(cmd_parts)
        logger.info(
            "claude_code_invoke",
            sandbox_id=sandbox_id[:12],
            prompt_length=len(prompt),
            prompt_preview=prompt[:200],
            system_prompt_length=len(system_prompt),
            max_turns=max_turns,
            allowed_tools=allowed_tools,
            command=full_cmd[:500],
            workdir=workdir,
        )

        result = await self._sandbox.execute(
            sandbox_id,
            SandboxJob(
                command=full_cmd,
                workdir=workdir,
                timeout_seconds=timeout,
            ),
        )

        logger.info(
            "claude_code_invoke_raw_result",
            sandbox_id=sandbox_id[:12],
            exit_code=result.exit_code,
            stdout_length=len(result.stdout),
            stdout_preview=result.stdout[:500],
            stderr_length=len(result.stderr),
            stderr_preview=result.stderr[:500],
        )

        if result.exit_code != 0:
            combined = result.stdout + result.stderr
            if "authentication_error" in combined:
                logger.error(
                    "claude_code_auth_error",
                    sandbox_id=sandbox_id[:12],
                    combined_preview=combined[:500],
                )
                raise ClaudeCodeCredentialError(TokenStatus.EXPIRED)

            logger.warning(
                "claude_code_invoke_failed",
                exit_code=result.exit_code,
                stdout_preview=result.stdout[:500],
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
            content_preview=parsed.get("content", "")[:300],
            usage=parsed.get("usage", {}),
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
            await _write_tmpfs_file(self._sandbox, sandbox_id, prompt_file, system_prompt)
            cmd_parts.extend(["--system-prompt", prompt_file])

        cmd_parts.append(shlex.quote(prompt))

        # Run claude and tee to file so we can tail it
        full_cmd = " ".join(cmd_parts) + f" > {output_file} 2>&1"

        logger.info(
            "claude_code_invoke_streaming",
            sandbox_id=sandbox_id[:12],
            prompt_length=len(prompt),
            prompt_preview=prompt[:200],
            system_prompt_length=len(system_prompt),
            max_turns=max_turns,
            invocation_id=invocation_id,
            command=full_cmd[:500],
            workdir=workdir,
            output_file=output_file,
            exit_file=exit_file,
        )

        # Write script via exec (not write_file) — /tmp is tmpfs, put_archive fails silently
        script = (
            f"#!/bin/sh\n"
            f"trap 'echo 130 > {exit_file}' INT TERM HUP\n"
            f"{full_cmd}\n"
            f"echo $? > {exit_file}\n"
        )
        await _write_tmpfs_file(self._sandbox, sandbox_id, script_file, script)

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
        # Start counting only after a grace period to allow claude to start up
        stale_polls = 0
        max_stale_polls = 5  # ~15s with STREAM_POLL_INTERVAL=3
        startup_grace_polls = 10  # ~30s grace period for claude to start

        consecutive_sandbox_errors = 0
        max_sandbox_errors = 3

        async def _poll_loop() -> None:
            """Poll output file until process completes or errors out."""
            nonlocal lines_seen, stale_polls, consecutive_sandbox_errors

            start_time = asyncio.get_event_loop().time()

            while True:
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                await asyncio.sleep(STREAM_POLL_INTERVAL)

                try:
                    # Check if process finished
                    exit_check = await self._sandbox.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"cat {exit_file} 2>/dev/null || echo running",
                            timeout_seconds=15,
                        ),
                    )
                    consecutive_sandbox_errors = 0
                except Exception:
                    consecutive_sandbox_errors += 1
                    logger.warning(
                        "claude_code_sandbox_error",
                        sandbox_id=sandbox_id[:12],
                        invocation_id=invocation_id,
                        consecutive_errors=consecutive_sandbox_errors,
                    )
                    if consecutive_sandbox_errors >= max_sandbox_errors:
                        logger.error(
                            "claude_code_sandbox_unreachable",
                            sandbox_id=sandbox_id[:12],
                            invocation_id=invocation_id,
                        )
                        if on_activity:
                            await on_activity("Sandbox unreachable — aborting")
                        return
                    continue

                process_done = exit_check.stdout.strip() != "running"

                # Read line count
                try:
                    tail_result = await self._sandbox.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"wc -l < {output_file}",
                            timeout_seconds=15,
                        ),
                    )
                    total_lines = int(tail_result.stdout.strip())
                except (ValueError, Exception):
                    total_lines = 0

                # Check for auth errors on first output
                if total_lines > 0 and lines_seen == 0:
                    peek = await self._sandbox.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"head -5 {output_file}",
                            timeout_seconds=10,
                        ),
                    )
                    peek_text = peek.stdout.lower()
                    if (
                        "authentication_error" in peek_text
                        or "oauth token has expired" in peek_text
                        or "token expired" in peek_text
                    ):
                        logger.error(
                            "claude_code_stream_auth_error",
                            sandbox_id=sandbox_id[:12],
                            invocation_id=invocation_id,
                            output_preview=peek.stdout[:300],
                        )
                        if on_activity:
                            await on_activity(
                                "AUTH_EXPIRED: OAuth token expired"
                                " — re-authenticate in sandbox"
                            )
                        return

                if total_lines > lines_seen:
                    stale_polls = 0
                    new_count = total_lines - lines_seen
                    logger.debug(
                        "claude_code_stream_new_lines",
                        sandbox_id=sandbox_id[:12],
                        invocation_id=invocation_id,
                        new_lines=new_count,
                        total_lines=total_lines,
                        elapsed=elapsed,
                    )
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
                        if activity:
                            logger.info(
                                "claude_code_stream_activity",
                                sandbox_id=sandbox_id[:12],
                                invocation_id=invocation_id,
                                activity=activity[:200],
                            )
                            if on_activity:
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
                    logger.debug(
                        "claude_code_stream_poll_idle",
                        sandbox_id=sandbox_id[:12],
                        invocation_id=invocation_id,
                        elapsed=elapsed,
                        total_lines=total_lines,
                        lines_seen=lines_seen,
                    )
                    polls_so_far = elapsed // STREAM_POLL_INTERVAL
                    if polls_so_far >= startup_grace_polls:
                        proc_check = await self._sandbox.execute(
                            sandbox_id,
                            SandboxJob(
                                command=(
                                    f"pgrep -f 'lintel-run-{invocation_id}'"
                                    f" >/dev/null 2>&1"
                                    f" || pgrep -f 'claude.*print'"
                                    f" >/dev/null 2>&1"
                                    f"; echo $?"
                                ),
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
                                return

                if process_done:
                    # Read any remaining lines before exiting
                    return

        try:
            await asyncio.wait_for(_poll_loop(), timeout=timeout + 30)
        except TimeoutError:
            logger.warning(
                "claude_code_streaming_hard_timeout",
                sandbox_id=sandbox_id[:12],
                invocation_id=invocation_id,
                timeout=timeout,
            )

        logger.info(
            "claude_code_stream_poll_done",
            sandbox_id=sandbox_id[:12],
            invocation_id=invocation_id,
            lines_streamed=lines_seen,
            content_parts=len(final_content_parts),
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

        logger.info(
            "claude_code_stream_final_output",
            sandbox_id=sandbox_id[:12],
            invocation_id=invocation_id,
            exit_code=exit_code,
            stdout_length=len(final_result.stdout),
            stdout_preview=final_result.stdout[:500],
        )

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
            invocation_id=invocation_id,
            exit_code=exit_code,
            content_length=len(parsed.get("content", "")),
            content_preview=parsed.get("content", "")[:300],
            lines_streamed=lines_seen,
            usage=parsed.get("usage", {}),
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
