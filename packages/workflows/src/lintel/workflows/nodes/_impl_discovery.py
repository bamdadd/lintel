"""Implementation helpers — dev-command discovery, skill loading, guidelines, and test utilities."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Dev-command discovery
# ---------------------------------------------------------------------------


async def discover_dev_commands(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, str, str, str]:
    """Discover test, lint, typecheck, and single-test commands.

    Returns (test_command, lint_command, typecheck_command, test_single_command).
    """
    from lintel.sandbox.types import SandboxJob

    # Check for Makefile targets
    make_check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="cat Makefile 2>/dev/null | head -300",
            workdir=workspace_path,
            timeout_seconds=10,
        ),
    )
    makefile = make_check.stdout

    # Detect project type and workspace structure
    detect = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"ls {workspace_path}/pyproject.toml {workspace_path}/package.json 2>/dev/null",
            workdir=workspace_path,
            timeout_seconds=5,
        ),
    )
    files = detect.stdout

    # Detect uv workspace
    is_workspace = False
    if "pyproject.toml" in files:
        ws_check = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"grep -c 'tool.uv.workspace' {workspace_path}/pyproject.toml"
                    " 2>/dev/null || echo 0"
                ),
                workdir=workspace_path,
                timeout_seconds=5,
            ),
        )
        is_workspace = ws_check.stdout.strip() not in ("0", "")

    # Defaults
    test_command = "make test-unit" if "test-unit:" in makefile else "make test"
    lint_command = "make lint" if "lint:" in makefile else "echo 'no lint configured'"
    typecheck_command = "make typecheck" if "typecheck:" in makefile else "echo 'no typecheck'"
    test_single_command = "uv run pytest <file> -v"

    if "pyproject.toml" in files:
        # Workspace projects: prefer test-affected (only tests changed packages)
        if is_workspace and "test-affected:" in makefile:
            test_command = "make test-affected"
        elif "test-unit:" not in makefile:
            test_command = "uv run pytest tests/unit -v -n auto"
        test_single_command = "uv run pytest <file> -v"
        if "lint:" not in makefile:
            lint_command = "uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/"
        if "typecheck:" not in makefile:
            typecheck_command = "uv run mypy src/"
    elif "package.json" in files:
        test_command = "npm test"
        lint_command = "npm run lint 2>/dev/null || echo 'no lint'"
        typecheck_command = "npx tsc --noEmit 2>/dev/null || echo 'no typecheck'"
        test_single_command = "npx jest <file>"

    return test_command, lint_command, typecheck_command, test_single_command


# ---------------------------------------------------------------------------
# Skill system-prompt loading
# ---------------------------------------------------------------------------


async def load_skill_system_prompt(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    skill_id: str,
    workspace_path: str,
    fallback_template: str,
    **format_kwargs: str,
) -> str:
    """Load a skill's system_prompt from the store, with template substitution.

    Falls back to ``fallback_template`` if the store is unavailable or the skill
    is not found.
    """
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    app_state = configurable.get("app_state")
    if app_state is None:
        run_id = state.get("run_id", "")
        if run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            app_state = get_app_state(run_id)

    skill_store = getattr(app_state, "skill_definition_store", None) if app_state else None

    prompt_template = ""
    if skill_store is not None:
        try:
            skill = await skill_store.get(skill_id)
            if skill is not None:
                raw = (
                    skill.system_prompt
                    if hasattr(skill, "system_prompt")
                    else skill.get("system_prompt", "")
                )
                if raw:
                    prompt_template = raw
                    logger.info("skill_prompt_loaded", skill_id=skill_id, length=len(raw))
        except Exception:
            logger.warning("skill_prompt_load_failed", skill_id=skill_id)

    if not prompt_template:
        prompt_template = fallback_template

    # Substitute template variables
    format_kwargs["workspace_path"] = workspace_path
    try:
        return prompt_template.format(**format_kwargs)
    except KeyError:
        # Template has placeholders the kwargs don't cover — return as-is
        return prompt_template


# ---------------------------------------------------------------------------
# Guideline / plan-file reading
# ---------------------------------------------------------------------------


async def read_guidelines(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> str:
    """Read project guidelines (CLAUDE.md, docs/agents.md) from sandbox."""
    from lintel.sandbox.types import SandboxJob

    guidelines = ""
    for guide_file in ("CLAUDE.md", "docs/agents.md"):
        try:
            result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=f"cat {workspace_path}/{guide_file} 2>/dev/null || true",
                    workdir=workspace_path,
                    timeout_seconds=10,
                ),
            )
            if result.stdout.strip():
                guidelines += f"\n\n## {guide_file}\n{result.stdout.strip()}"
        except Exception:
            pass
    return guidelines


async def pre_read_plan_files(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    file_paths: list[str],
) -> dict[str, str]:
    """Read files referenced in the plan.

    Returns {relative_path: content} for files that exist.
    Skips files that don't exist (agent will create them).
    """
    max_file_size = 10_000
    contents: dict[str, str] = {}
    seen: set[str] = set()

    for rel_path in file_paths:
        if rel_path in seen:
            continue
        seen.add(rel_path)

        abs_path = f"{workspace_path}/{rel_path}" if not rel_path.startswith("/") else rel_path
        try:
            content = await sandbox_manager.read_file(sandbox_id, abs_path)
            if len(content) > max_file_size:
                content = content[:max_file_size] + "\n... (truncated)"
            contents[rel_path] = content
        except Exception:
            pass

    return contents


# ---------------------------------------------------------------------------
# Test output logging
# ---------------------------------------------------------------------------


async def log_test_output(
    test_output: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> None:
    """Log test output to pipeline stage logs, extracting the failure summary."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    if not test_output.strip():
        return

    # Extract the most useful part: pytest short summary or last N lines
    lines = test_output.strip().split("\n")

    # Look for pytest short test summary
    summary_start = None
    for i, line in enumerate(lines):
        if "short test summary" in line.lower() or "FAILED" in line:
            summary_start = i
            break

    if summary_start is not None:
        # Include from summary to end, capped at 30 lines
        summary_lines = lines[summary_start : summary_start + 30]
        summary = "\n".join(summary_lines)
    else:
        # Just show the last 20 lines
        summary = "\n".join(lines[-20:])

    # Cap total length for the log entry
    if len(summary) > 3000:
        summary = summary[:3000] + "\n...(truncated)"

    await tracker.append_log("implement", f"Test output:\n```\n{summary}\n```")


# ---------------------------------------------------------------------------
# Shared test/lint execution helpers
# ---------------------------------------------------------------------------


async def stream_execute_with_logging(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    command: str,
    workdir: str,
    timeout_seconds: int,
    log_fn: Callable[[str], Awaitable[None]],
) -> tuple[str, int]:
    """Execute a command with real-time log streaming.

    If the sandbox supports ``execute_stream()``, yields lines to ``log_fn``
    as they arrive. Otherwise falls back to blocking ``execute()`` and logs
    output after completion.

    Returns ``(full_output, exit_code)`` — same contract as the old blocking path.
    """
    from lintel.sandbox.types import SandboxJob

    stream_fn = getattr(sandbox_manager, "execute_stream", None)
    if stream_fn is None or not callable(stream_fn):
        # Fallback: blocking execute
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=command, workdir=workdir, timeout_seconds=timeout_seconds),
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            stripped = line.strip()
            if stripped:
                await log_fn(stripped)
        return output, result.exit_code

    # Streaming path
    job = SandboxJob(command=command, workdir=workdir, timeout_seconds=timeout_seconds)
    output_lines: list[str] = []
    exit_code = -1

    async for line in await stream_fn(sandbox_id, job):
        if line.startswith("__EXIT:") and line.endswith("__"):
            exit_code = int(line[7:-2])
        else:
            output_lines.append(line)
            await log_fn(line)

    return "\n".join(output_lines), exit_code


async def failures_in_agent_files(
    test_output: str,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> bool:
    """Check if any test failures are in files the agent created or modified.

    Parses FAILED lines from pytest output (e.g. ``FAILED path/to/test.py::...``)
    and checks if those files are in the set of agent-changed files.
    Returns True if any failure is in an agent-changed file.
    """
    import re

    from lintel.sandbox.types import SandboxJob

    # Extract failed test file paths from pytest output
    failed_files: set[str] = set()
    for match in re.finditer(r"FAILED\s+([\w/._-]+\.py)::", test_output):
        failed_files.add(match.group(1))
    # Also catch ERROR lines (import failures)
    for match in re.finditer(r"ERROR\s+([\w/._-]+\.py)", test_output):
        failed_files.add(match.group(1))

    if not failed_files:
        # Can't parse failures — assume agent is responsible
        return True

    # Get agent-changed files
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "{ git diff --name-only origin/main 2>/dev/null;"
                " git diff --name-only main 2>/dev/null;"
                " git status --porcelain 2>/dev/null | awk '{print $NF}';"
                " } | sort -u || true"
            ),
            workdir=workspace_path,
            timeout_seconds=10,
        ),
    )
    agent_files = {f.strip() for f in result.stdout.strip().split("\n") if f.strip()}

    return any(failed in agent_files for failed in failed_files)


async def auto_format(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    tracker: Any,  # noqa: ANN401
) -> None:
    """Run code formatters in the sandbox to fix agent-generated lint issues."""
    from lintel.sandbox.types import SandboxJob

    await tracker.append_log("implement", "Auto-fixing lint: make format")
    try:
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command="make format 2>&1 | tail -5",
                workdir=workspace_path,
                timeout_seconds=60,
            ),
        )
        # Always run --unsafe-fixes after make format (TC001 etc. need it)
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "ruff check --fix --unsafe-fixes . 2>/dev/null; ruff format . 2>/dev/null; true"
                ),
                workdir=workspace_path,
                timeout_seconds=30,
            ),
        )
    except Exception:
        logger.warning("implement_auto_format_failed", exc_info=True)


async def run_tests(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, int]:
    """Run tests in the sandbox. Returns (output, exit_code)."""
    from lintel.sandbox.types import SandboxJob
    from lintel.skills_api.domain.discover_test_command import discover_test_command
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)

    # Pull latest from origin before running tests so we pick up any
    # fixes that landed on the base branch after the sandbox was created.
    base_branch = state.get("repo_branch", "main")
    try:
        pull_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "git stash -q 2>/dev/null;"
                    f" git pull --rebase origin {base_branch} 2>&1 || true;"
                    " git stash pop -q 2>/dev/null || true"
                ),
                workdir=workspace_path,
                timeout_seconds=60,
            ),
        )
        await tracker.append_log("implement", f"git pull: {pull_result.stdout[:80]}")
    except Exception:
        logger.warning("implement_git_pull_failed")

    # Discover test command
    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workspace_path)
    except Exception:
        logger.warning("implement_test_discovery_failed")
        return "Test discovery failed", 1

    test_command = discovery["test_command"]
    setup_commands: list[str] = discovery.get("setup_commands", [])

    # Run setup (dep install)
    for cmd in setup_commands:
        await tracker.append_log("implement", f"Setup: {cmd[:60]}")
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=cmd, workdir=workspace_path, timeout_seconds=180),
        )

    async def _log_test_line(line: str) -> None:
        await tracker.append_log("implement", line)

    await tracker.append_log("implement", f"Running tests: {test_command[:80]}")
    try:
        output, exit_code = await stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            test_command,
            workspace_path,
            600,
            _log_test_line,
        )
    except Exception:
        logger.warning("implement_test_execute_failed")
        return "Test execution failed", 1

    if exit_code != 0:
        # Check if failures are only in pre-existing tests (not agent-changed files).
        # If so, accept — the agent's code didn't introduce regressions.
        failed_in_agent_files = await failures_in_agent_files(
            output, sandbox_manager, sandbox_id, workspace_path
        )
        if not failed_in_agent_files:
            await tracker.append_log(
                "implement",
                "Test failures are in pre-existing files only — accepting",
            )
            exit_code = 0

    verdict = "PASSED" if exit_code == 0 else "FAILED"
    await tracker.append_log("implement", f"Tests: {verdict}")

    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    return output, exit_code


async def run_lint(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, int]:
    """Run lint in the sandbox. Returns (output, exit_code)."""
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    (
        _test_command,
        lint_command,
        _typecheck_command,
        _test_single_command,
    ) = await discover_dev_commands(sandbox_manager, sandbox_id, workspace_path)

    # Auto-fix lint issues before checking (ruff format + ruff check --fix)
    format_command = (
        "make format"
        if "format:"
        in (
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command="grep -c 'format:' Makefile 2>/dev/null || echo 0",
                    workdir=workspace_path,
                    timeout_seconds=5,
                ),
            )
        ).stdout
        else "ruff check --fix --unsafe-fixes . 2>/dev/null; ruff format . 2>/dev/null; true"
    )
    await tracker.append_log("implement", f"Auto-fixing lint: {format_command[:60]}")
    try:
        fix_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=format_command, workdir=workspace_path, timeout_seconds=120),
        )
        if fix_result.stdout.strip():
            for line in fix_result.stdout.strip().splitlines()[-10:]:
                await tracker.append_log("implement", line.strip())
    except Exception:
        logger.warning("implement_lint_fix_failed")

    # Always run --unsafe-fixes to catch TC001 etc. that make format misses
    try:
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "ruff check --fix --unsafe-fixes . 2>/dev/null; ruff format . 2>/dev/null; true"
                ),
                workdir=workspace_path,
                timeout_seconds=30,
            ),
        )
    except Exception:
        logger.warning("implement_unsafe_fix_failed")

    await tracker.append_log("implement", f"Running lint: {lint_command[:80]}")

    async def _log_lint_line(line: str) -> None:
        await tracker.append_log("implement", line)

    try:
        output, exit_code = await stream_execute_with_logging(
            sandbox_manager,
            sandbox_id,
            lint_command,
            workspace_path,
            120,
            _log_lint_line,
        )
    except Exception:
        logger.warning("implement_lint_execute_failed")
        return "Lint execution failed", 1

    verdict = "PASSED" if exit_code == 0 else "FAILED"
    await tracker.append_log("implement", f"Lint: {verdict}")

    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    return output, exit_code


# ---------------------------------------------------------------------------
# Fix-failures helper (structured path)
# ---------------------------------------------------------------------------


def _format_tool_preview(tool: str, args: dict[str, Any], result: str) -> str:
    """Format a tool result into a concise log line."""
    if not result:
        return ""

    if tool == "read_file":
        path = args.get("path", "")
        fname = path.split("/")[-1] if path else "file"
        lines = result.strip().split("\n")
        return f"{fname} ({len(lines)} lines)"

    if tool == "write_file":
        path = args.get("path", "")
        fname = path.split("/")[-1] if path else "file"
        lines = args.get("content", "").strip().split("\n")
        return f"{fname} ({len(lines)} lines written)"

    if tool == "execute_command":
        cmd = args.get("command", "")
        short_cmd = cmd[:60]
        out_lines = [ln.strip() for ln in result.strip().split("\n") if ln.strip()]
        output = out_lines[0][:80] if out_lines else "(no output)"
        return f"`{short_cmd}` -> {output}"

    return result[:120].replace("\n", " ")


FIX_SYSTEM_PROMPT = """\
You are a senior software engineer fixing test failures.
The workspace is at: {workspace_path}

The tests failed with the output below. Fix the code using sandbox_write_file \
and sandbox_read_file. Do NOT explore the codebase — fix only what's broken.

STOP as soon as the fix is written. Do NOT run tests yourself.
"""


async def fix_failures(
    agent_runtime: AgentRuntime,
    thread_ref: ThreadRef,
    workspace_path: str,
    test_output: str,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> dict[str, Any]:
    """Give the LLM test failures and let it fix with a focused tool loop."""
    from lintel.agents.sandbox_tools import sandbox_tool_schemas
    from lintel.agents.types import AgentRole
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)

    async def _on_tool_call(
        iteration: int,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: str,
    ) -> None:
        short_name = tool_name.replace("sandbox_", "")
        preview = _format_tool_preview(short_name, tool_args, tool_result)
        await tracker.append_log("implement", f"  fix [{iteration}] {short_name}: {preview}")

    return await agent_runtime.execute_step(
        thread_ref=thread_ref,
        agent_role=AgentRole.CODER,
        step_name="implement_fix",
        messages=[
            {
                "role": "system",
                "content": FIX_SYSTEM_PROMPT.format(workspace_path=workspace_path),
            },
            {
                "role": "user",
                "content": f"## Test Failures\n```\n{test_output}\n```\n\nFix the code.",
            },
        ],
        tools=sandbox_tool_schemas(exclude={"sandbox_list_files", "sandbox_execute_command"}),
        sandbox_manager=sandbox_manager,
        sandbox_id=sandbox_id,
        max_iterations=10,
        on_tool_call=_on_tool_call,
        run_id=state.get("run_id", ""),
    )


# ---------------------------------------------------------------------------
# JSON file output parsing (structured path)
# ---------------------------------------------------------------------------


def parse_file_output(content: str) -> dict[str, Any]:
    """Parse LLM output into {path: content} dict.

    Expects JSON: {"files": {"path": "content", ...}}
    Falls back to extracting from markdown fences.
    """
    # Try direct JSON
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            files: dict[str, Any] = data.get("files", data)
            return files
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown fences
    for fence in ("```json", "```"):
        idx = content.find(fence)
        if idx == -1:
            continue
        after = content[idx + len(fence) :]
        end = after.rfind("```")
        json_str = after[:end].strip() if end != -1 else after.strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                files = data.get("files", data)
                return dict(files)
        except json.JSONDecodeError:
            continue

    # Try finding { ... } block
    first = content.find("{")
    if first != -1:
        last = content.rfind("}")
        if last > first:
            try:
                data = json.loads(content[first : last + 1])
                if isinstance(data, dict):
                    files = data.get("files", data)
                    return dict(files)
            except json.JSONDecodeError:
                pass

    return {}
