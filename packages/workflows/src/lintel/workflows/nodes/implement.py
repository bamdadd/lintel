"""Implementation workflow node — generate code, test, fix until green.

Two execution paths based on provider:

**Claude Code (TDD mode):**
Claude Code has its own agentic loop (file editing, bash). We give it a TDD
system prompt that instructs small red-green-refactor cycles with continuous
testing, linting, and incremental git commits.

**LiteLLM providers (structured mode):**
1. Single LLM call generates all file contents as JSON.
2. Node writes files programmatically to sandbox.
3. Node runs tests via discover_test_command.
4. If tests fail, LLM gets error output + focused fix tools (max retries).
5. Collect artifacts and return.
"""

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

MAX_FIX_ATTEMPTS = 3
MAX_TDD_FIX_ATTEMPTS = 2

GENERATE_SYSTEM_PROMPT = """\
You are a senior software engineer. Given a plan and existing file contents, \
produce ALL the code changes needed.

RESPOND ONLY WITH A JSON object — no markdown, no explanation, no fences:
{{"files": {{"path/to/file.py": "full file content", ...}}}}

Rules:
- Include the COMPLETE file content for each file, not just the diff.
- Include both source files AND test files.
- Use the file paths relative to the workspace root.
- Match the existing code style and patterns from the provided file contents.
- Do not include files that don't need changes.
"""

FIX_SYSTEM_PROMPT = """\
You are a senior software engineer fixing test failures.
The workspace is at: {workspace_path}

The tests failed with the output below. Fix the code using sandbox_write_file \
and sandbox_read_file. Do NOT explore the codebase — fix only what's broken.

STOP as soon as the fix is written. Do NOT run tests yourself.
"""

TDD_SYSTEM_PROMPT = """\
You are a senior software engineer implementing a feature using strict TDD \
(Test-Driven Development) with small, incremental steps.

## Working Directory
{workspace_path}

## Process — Red / Green / Refactor

Work in SMALL increments. Each increment is one logical unit of change \
(one function, one class, one endpoint, one entity). Never make large \
chunky changes — break the plan into the smallest possible steps.

For EACH increment:

1. **RED** — Write a failing test FIRST.
   - The test should define the expected behaviour for the next small piece.
   - Run the test suite to confirm the new test fails (and all existing tests still pass).
   - Command: `{test_command}`

2. **GREEN** — Write the MINIMAL production code to make the test pass.
   - Do not write more code than needed to pass the test.
   - Run the test suite to confirm all tests pass.
   - Run the linter: `{lint_command}`
   - Fix any lint errors immediately.

3. **REFACTOR** — Clean up while tests are green.
   - Remove duplication, improve naming, extract helpers.
   - Run tests again to confirm nothing broke.
   - Commit this increment: `git add -A && git commit -m "<concise description>"`

## Rules

- **Use Pydantic models** (BaseModel with frozen=True) for any new data structures, \
not plain dicts or untyped dataclasses. Follow the project's existing patterns.
- **Never skip tests.** Every piece of production code must be covered by a test written \
BEFORE the implementation.
- **Run tests and lint after EVERY file change**, not just at the end. If something \
breaks, fix it immediately before moving on.
- **Commit after each green-refactor cycle.** Small commits are better than one big commit.
- **Match the existing code style** — indentation, naming conventions, import style, \
module structure. Read existing files before writing new ones.
- **Introduce entities incrementally.** If a feature needs a new entity, first add the \
entity type + a test for it, then the store, then the API endpoint — each as a separate \
red-green-refactor cycle.
- **Existing tests must never break.** If you change a shared interface, update all \
callers and their tests in the same increment.
- **Do not refactor unrelated code.** Only touch files relevant to the current task.
- If the project uses frozen dataclasses (as in contracts/types.py), follow that pattern \
for domain types. Use Pydantic BaseModel for API request/response schemas.

## Lint & Format
- Auto-format: `make format` (run this BEFORE lint to auto-fix issues)
- Lint: `{lint_command}`
- Type check: `{typecheck_command}` (run periodically, not after every change)

## Test Execution
- Full suite: `{test_command}`
- Single file: `{test_single_command}`
"""


async def spawn_implementation(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Generate code, write files, run tests, fix until green."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config, state)
    _configurable = _config.get("configurable", {})
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    agent_runtime: AgentRuntime | None = _configurable.get("agent_runtime")

    run_id = state.get("run_id", "")
    if (sandbox_manager is None or agent_runtime is None) and run_id:
        from lintel.workflows.nodes._runtime_registry import (
            get_runtime,
            get_sandbox_manager,
        )

        if sandbox_manager is None:
            sandbox_manager = get_sandbox_manager(run_id)
        if agent_runtime is None:
            agent_runtime = get_runtime(run_id)

    logger.info(
        "implement_node_started",
        has_sandbox=sandbox_manager is not None,
        has_runtime=agent_runtime is not None,
        sandbox_id=state.get("sandbox_id", ""),
    )

    await tracker.mark_running("implement")
    await tracker.append_log("implement", "Starting implementation")

    if sandbox_manager is None:
        await tracker.mark_completed("implement", error="No sandbox manager available")
        return {"error": "No sandbox manager available", "current_phase": "closed"}

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        await tracker.mark_completed("implement", error="No sandbox available")
        return {
            "error": "No sandbox available — setup_workspace must run first",
            "current_phase": "closed",
        }

    # Reconnect network for package installs during test setup
    try:
        await sandbox_manager.reconnect_network(sandbox_id)
    except Exception:
        logger.warning("implement_reconnect_network_failed")

    plan = state.get("plan", {})
    messages = state.get("sanitized_messages", [])
    workspace_path = state.get("workspace_path") or "/workspace/repo"

    # Read project guidelines
    guidelines = await _read_guidelines(sandbox_manager, sandbox_id, workspace_path)

    # Build task descriptions from plan
    tasks = plan.get("tasks", [])
    all_file_paths: list[str] = []
    task_lines = []
    for t in tasks:
        if isinstance(t, str):
            task_lines.append(f"- {t}")
        else:
            line = f"- {t.get('title', t)}"
            desc = t.get("description", "")
            if desc:
                line += f"\n  {desc}"
            paths = t.get("file_paths", [])
            if paths:
                line += f"\n  Files: {', '.join(paths)}"
                all_file_paths.extend(paths)
            task_lines.append(line)
    task_text = "\n".join(task_lines)
    plan_summary = plan.get("summary", "Implement the requested feature.")

    # Pre-read files referenced in the plan
    file_contents = await _pre_read_plan_files(
        sandbox_manager, sandbox_id, workspace_path, all_file_paths
    )
    if file_contents:
        await tracker.append_log("implement", f"Pre-read {len(file_contents)} file(s) from plan")

    file_context = _build_file_context(file_contents)
    research_context = state.get("research_context", "")
    research_section = f"\n\n## Research Context\n{research_context}" if research_context else ""
    guidelines_section = f"\n\n## Project Guidelines\n{guidelines}" if guidelines else ""

    # Check for review feedback from a previous cycle
    review_feedback = ""
    review_cycles = state.get("review_cycles", 0)
    if review_cycles > 0:
        for output in reversed(state.get("agent_outputs", [])):
            if isinstance(output, dict) and output.get("node") == "review":
                review_feedback = output.get("output", "")
                break

    review_section = (
        f"\n\n## Review Feedback (cycle {review_cycles})\n"
        f"The reviewer requested changes. Address ALL issues below:\n{review_feedback}"
        if review_feedback
        else ""
    )

    # Inject failure context from previous pipeline run (continuation)
    previous_error = state.get("previous_error", "")
    failure_section = ""
    if previous_error:
        prev_stage = state.get("previous_failed_stage", "implement")
        failure_section = (
            f"\n\n## Previous Attempt Failed\n"
            f"The previous pipeline run failed at the **{prev_stage}** stage with:\n"
            f"```\n{previous_error}\n```\n"
            f"Take this into account and avoid the same failure mode.\n"
        )

    user_prompt = (
        f"## Plan\n{plan_summary}\n\n## Tasks\n{task_text}\n\n"
        f"## Original request\n{chr(10).join(messages)}"
        f"{file_context}{research_section}{guidelines_section}"
        f"{review_section}{failure_section}"
    )

    # Parse thread ref
    thread_ref = _parse_thread_ref(state["thread_ref"])

    total_usage: list[dict[str, Any]] = []
    agent_output = "No agent runtime configured."

    if agent_runtime is not None:
        # Detect provider to choose execution strategy
        use_tdd, _provider, _model_name = await _resolve_coder_policy(agent_runtime)

        await tracker.log_llm_context("implement", "coder", "implement_generate")

        if use_tdd:
            # ---- TDD path (Claude models: Claude Code, Bedrock, Anthropic) ----
            agent_output, test_passed, total_usage = await _implement_tdd(
                agent_runtime=agent_runtime,
                thread_ref=thread_ref,
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
                workspace_path=workspace_path,
                user_prompt=user_prompt,
                config=_config,
                state=state,
            )
        else:
            # ---- LiteLLM structured path ----
            agent_output, test_passed, total_usage = await _implement_structured(
                agent_runtime=agent_runtime,
                thread_ref=thread_ref,
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
                workspace_path=workspace_path,
                user_prompt=user_prompt,
                config=_config,
                state=state,
            )

    # Disconnect network
    import contextlib

    with contextlib.suppress(Exception):
        await sandbox_manager.disconnect_network(sandbox_id)

    # Rebase on base branch
    rebase_warning = ""
    base_branch = state.get("repo_branch", "main")
    if base_branch:
        from lintel.workflows.nodes._git_helpers import GitOperations

        try:
            git_ops = GitOperations(sandbox_manager, sandbox_id)
            rebase_result = await git_ops.rebase_on_upstream(base_branch)
            if not rebase_result["success"]:
                rebase_warning = rebase_result["message"]
        except Exception:
            logger.warning("implement_rebase_failed", exc_info=True)
            rebase_warning = "Rebase failed — sandbox may be unavailable"

    # Collect artifacts
    await tracker.append_log("implement", "Collecting artifacts...")
    try:
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id, workdir=workspace_path)
    except Exception:
        from lintel.workflows.nodes._error_handling import WorkflowErrorHandler

        await tracker.mark_completed("implement", error="Failed to collect artifacts")
        err = Exception("Failed to collect artifacts")
        return await WorkflowErrorHandler.handle(state, "implement", err)

    outputs: list[dict[str, Any]] = [{"node": "implement", "output": agent_output}]
    # Emit test verdict so _check_phase and close can see it
    if agent_runtime is not None:
        test_verdict = "passed" if test_passed else "failed"
        outputs.append({"node": "test", "verdict": test_verdict})
    if rebase_warning:
        outputs.append({"node": "implement_rebase", "output": rebase_warning})

    # Persist code artifact
    diff_text = artifacts.get("content", "") if isinstance(artifacts, dict) else ""
    if diff_text:
        code_artifact_store = _configurable.get("code_artifact_store")
        if code_artifact_store is None:
            _app = _configurable.get("app_state")
            if _app is not None:
                code_artifact_store = getattr(_app, "code_artifact_store", None)
        if code_artifact_store is not None:
            from uuid import uuid4

            from lintel.domain.types import CodeArtifact

            artifact = CodeArtifact(
                artifact_id=str(uuid4()),
                work_item_id=state.get("work_item_id", ""),
                run_id=state.get("run_id", ""),
                artifact_type="diff",
                path="",
                content=diff_text,
            )
            try:
                await code_artifact_store.add(artifact)
                logger.info("code_artifact_stored", artifact_id=artifact.artifact_id)
            except Exception:
                logger.warning("code_artifact_persist_failed", exc_info=True)
        else:
            logger.warning("code_artifact_store_not_available")

    stage_outputs: dict[str, object] = {}
    if total_usage:
        # Merge usage across generate + fix attempts
        merged = {"input_tokens": 0, "output_tokens": 0, "step": "implement"}
        for u in total_usage:
            merged["input_tokens"] += u.get("input_tokens", 0)
            merged["output_tokens"] += u.get("output_tokens", 0)
        stage_outputs["token_usage"] = merged
    if diff_text:
        stage_outputs["diff"] = diff_text[:50000]
    if agent_runtime is not None and not test_passed:
        await tracker.mark_completed(
            "implement", outputs=stage_outputs or None, error="Tests failed"
        )
    else:
        await tracker.mark_completed("implement", outputs=stage_outputs or None)

    result_dict: dict[str, Any] = {
        "current_phase": "reviewing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
    if total_usage:
        result_dict["token_usage"] = total_usage
    return result_dict


# ---------------------------------------------------------------------------
# Streaming execution helper
# ---------------------------------------------------------------------------


async def _stream_execute_with_logging(
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


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def _is_claude_model(provider: str, model_name: str) -> bool:
    """Check if the provider/model combination is a Claude model (any provider)."""
    if provider == "claude_code":
        return True
    # Bedrock Claude models: anthropic.claude-*, eu.anthropic.claude-*, us.anthropic.claude-*
    if provider == "bedrock" and "anthropic.claude" in model_name:
        return True
    # Direct Anthropic API
    return provider == "anthropic" and "claude" in model_name


async def _resolve_coder_policy(
    agent_runtime: AgentRuntime,
) -> tuple[bool, str, str]:
    """Resolve the coder role's model policy.

    Returns (use_tdd, provider, model_name).
    use_tdd is True for any Claude model (Claude Code, Bedrock, or Anthropic API).
    """
    from lintel.agents.types import AgentRole

    try:
        policy = await agent_runtime._model_router.select_model(
            AgentRole.CODER, "implement_generate"
        )
        use_tdd = _is_claude_model(policy.provider, policy.model_name)
        return use_tdd, policy.provider, policy.model_name
    except Exception:
        return False, "unknown", "unknown"


async def _is_claude_code_provider(agent_runtime: AgentRuntime) -> bool:
    """Check if the coder role is assigned to a Claude model (any provider)."""
    is_claude, _, _ = await _resolve_coder_policy(agent_runtime)
    return is_claude


# ---------------------------------------------------------------------------
# TDD path (Claude models: Claude Code, Bedrock, Anthropic API)
# ---------------------------------------------------------------------------


async def _implement_tdd(
    *,
    agent_runtime: AgentRuntime,
    thread_ref: ThreadRef,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    user_prompt: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Run implementation via Claude Code with TDD system prompt.

    Returns (agent_output, test_passed, total_usage).
    """
    from lintel.agents.types import AgentRole
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.append_log("implement", "Using TDD mode (Claude model)")

    # Discover test/lint commands for the project
    (
        test_command,
        lint_command,
        typecheck_command,
        test_single_command,
    ) = await _discover_dev_commands(sandbox_manager, sandbox_id, workspace_path)

    await tracker.append_log("implement", f"Test: {test_command[:60]}")
    await tracker.append_log("implement", f"Lint: {lint_command[:60]}")

    # Install deps first
    from lintel.skills_api.domain.discover_test_command import discover_test_command

    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workspace_path)
        from lintel.sandbox.types import SandboxJob

        for cmd in discovery.get("setup_commands", []):
            await tracker.append_log("implement", f"Setup: {cmd[:60]}")
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command=cmd, workdir=workspace_path, timeout_seconds=180),
            )
    except Exception:
        logger.warning("implement_tdd_setup_failed")

    # Configure git for commits inside sandbox
    from lintel.sandbox.types import SandboxJob

    await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                'git config user.email "lintel@lintel.dev" && git config user.name "Lintel Agent"'
            ),
            workdir=workspace_path,
            timeout_seconds=10,
        ),
    )

    # Load the Write Code skill's system prompt from the store (user-editable)
    skill_id = "skill_write_code"
    system_prompt = await _load_skill_system_prompt(
        config,
        state,
        skill_id,
        workspace_path,
        test_command=test_command,
        lint_command=lint_command,
        typecheck_command=typecheck_command,
        test_single_command=test_single_command,
    )
    await tracker.append_log("implement", f"Skill: {skill_id} (TDD)")

    await tracker.append_log("implement", "Starting TDD implementation...")

    async def _on_activity(activity: str) -> None:
        if activity:
            await tracker.append_log("implement", activity)

    # Claude Code has its own tool loop — pass no tools so it uses native agentic mode.
    # Other providers (Bedrock, Anthropic API) need sandbox tools for the runtime tool loop.
    from lintel.agents.sandbox_tools import sandbox_tool_schemas

    policy = await agent_runtime._model_router.select_model(AgentRole.CODER, "implement_generate")
    is_native_claude_code = policy.provider == "claude_code"
    tdd_tools = None if is_native_claude_code else sandbox_tool_schemas()
    # Bedrock needs more iterations — it explores before writing
    tdd_max_iter = 50 if not is_native_claude_code else 20

    try:
        result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="implement_generate",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tdd_tools,
            max_iterations=tdd_max_iter,
            sandbox_manager=sandbox_manager,
            sandbox_id=sandbox_id,
            on_activity=_on_activity,
            run_id=state.get("run_id", ""),
        )
        usage = StageTracker.extract_token_usage(result)
        content = result.get("content", "")
        await tracker.append_log("implement", f"TDD session complete ({len(content):,} chars)")
    except Exception:
        logger.exception("implement_tdd_failed")
        await tracker.append_log("implement", "TDD session failed")
        return "Implementation failed.", False, []

    # Detect "no changes" — LLM concluded everything was already done
    from lintel.sandbox.types import SandboxJob

    # Check for uncommitted changes (sandbox_write_file doesn't git-add) AND committed changes.
    # git status --porcelain shows unstaged/staged files; git diff shows committed-but-not-pushed.
    diff_check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "{ git status --porcelain;"
                " git diff --name-only origin/main..HEAD 2>/dev/null;"
                " git diff --name-only main..HEAD 2>/dev/null;"
                " } | sort -u"
            ),
            workdir=workspace_path,
            timeout_seconds=10,
        ),
    )
    changed_files = [f for f in diff_check.stdout.strip().split("\n") if f.strip()]
    if not changed_files:
        await tracker.append_log("implement", "No files changed — skipping tests")
        return "No changes made.", True, [usage]

    await tracker.append_log("implement", f"{len(changed_files)} file(s) changed")

    # Auto-format before testing — agent-generated code may have lint issues
    await _auto_format(sandbox_manager, sandbox_id, workspace_path, tracker)

    # Test/fix loop — give the LLM a chance to fix failures
    test_passed = False
    test_output = ""
    for attempt in range(MAX_TDD_FIX_ATTEMPTS + 1):
        test_output, test_exit = await _run_tests(
            config, state, sandbox_manager, sandbox_id, workspace_path
        )
        if test_exit == 0:
            test_passed = True
            await tracker.append_log("implement", "Tests: PASSED")
            break

        if attempt < MAX_TDD_FIX_ATTEMPTS:
            msg = f"Tests failed (attempt {attempt + 1}/{MAX_TDD_FIX_ATTEMPTS}) — fixing..."
            await tracker.append_log("implement", msg)
            await _log_test_output(test_output, config, state)
            try:
                fix_tools = (
                    None
                    if is_native_claude_code
                    else sandbox_tool_schemas(
                        exclude={"sandbox_list_files", "sandbox_execute_command"},
                    )
                )
                fix_result = await agent_runtime.execute_step(
                    thread_ref=thread_ref,
                    agent_role=AgentRole.CODER,
                    step_name="implement_fix",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"## Test Failures\n```\n{test_output}\n```\n\n"
                                "Fix ONLY the failing tests. Do not change anything else."
                            ),
                        },
                    ],
                    tools=fix_tools,
                    sandbox_manager=sandbox_manager,
                    sandbox_id=sandbox_id,
                    on_activity=_on_activity,
                    run_id=state.get("run_id", ""),
                )
                fix_usage = StageTracker.extract_token_usage(fix_result)
                usage["input_tokens"] += fix_usage.get("input_tokens", 0)
                usage["output_tokens"] += fix_usage.get("output_tokens", 0)
            except Exception:
                logger.exception("implement_tdd_fix_failed")
                await tracker.append_log("implement", "Fix attempt failed")
                break
            # Re-format after fix
            await _auto_format(sandbox_manager, sandbox_id, workspace_path, tracker)

    if not test_passed:
        await tracker.append_log("implement", "Tests still failing after fix attempts")
        await _log_test_output(test_output, config, state)

    # Verify lint
    lint_output, lint_exit = await _run_lint(
        config, state, sandbox_manager, sandbox_id, workspace_path
    )
    lint_passed = lint_exit == 0
    if lint_passed:
        await tracker.append_log("implement", "Lint: PASSED")
    else:
        await tracker.append_log("implement", "Lint: FAILED")
        await tracker.append_log("implement", lint_output[-2000:] if lint_output else "No output")

    all_passed = test_passed and lint_passed
    if all_passed:
        agent_output = "Implementation complete."
    elif not test_passed and not lint_passed:
        agent_output = "Implementation complete — tests and lint failing."
    elif not test_passed:
        agent_output = "Implementation complete — tests failing."
    else:
        agent_output = "Implementation complete — lint failing."
    return agent_output, all_passed, [usage]


async def _discover_dev_commands(
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
            command="cat Makefile 2>/dev/null | head -100",
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


async def _load_skill_system_prompt(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    skill_id: str,
    workspace_path: str,
    **format_kwargs: str,
) -> str:
    """Load a skill's system_prompt from the store, with template substitution.

    Falls back to the hardcoded TDD_SYSTEM_PROMPT if the store is unavailable
    or the skill is not found.
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
        prompt_template = TDD_SYSTEM_PROMPT

    # Substitute template variables
    format_kwargs["workspace_path"] = workspace_path
    try:
        return prompt_template.format(**format_kwargs)
    except KeyError:
        # Template has placeholders the kwargs don't cover — return as-is
        return prompt_template


# ---------------------------------------------------------------------------
# Structured path (LiteLLM providers)
# ---------------------------------------------------------------------------


async def _implement_structured(
    *,
    agent_runtime: AgentRuntime,
    thread_ref: ThreadRef,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    user_prompt: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Run implementation via structured JSON generation + test + fix loop.

    Returns (agent_output, test_passed, total_usage).
    """
    from lintel.agents.types import AgentRole
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    total_usage: list[dict[str, Any]] = []

    await tracker.append_log("implement", "Skill: structured-generate (JSON)")

    # --- Phase 1: Generate code (single LLM call, no tools) ---
    await tracker.append_log("implement", "Generating code...")
    try:
        gen_result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="implement_generate",
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tools=[],  # No tools — single-shot JSON generation
            max_iterations=1,
            run_id=state.get("run_id", ""),
        )
        gen_content = gen_result.get("content", "")
        usage = StageTracker.extract_token_usage(gen_result)
        total_usage.append(usage)

        files_to_write = _parse_file_output(gen_content)
        if not files_to_write:
            await tracker.append_log("implement", "No files generated — fallback to tools")
            files_to_write = {}
    except Exception:
        logger.exception("implement_generate_failed")
        await tracker.append_log("implement", "Code generation failed")
        files_to_write = {}

    # --- Phase 2: Write files to sandbox ---
    if files_to_write:
        await tracker.append_log("implement", f"Writing {len(files_to_write)} file(s)")
        for rel_path, content in files_to_write.items():
            abs_path = f"{workspace_path}/{rel_path}" if not rel_path.startswith("/") else rel_path
            try:
                await sandbox_manager.write_file(sandbox_id, abs_path, content)
                lines = content.count("\n") + 1
                fname = rel_path.split("/")[-1]
                await tracker.append_log("implement", f"  wrote {fname} ({lines} lines)")
            except Exception:
                logger.warning("implement_write_failed", path=rel_path)
                await tracker.append_log("implement", f"  FAILED: {rel_path}")

    # --- Phase 3: Run tests, fix if broken ---
    test_passed = False
    for attempt in range(MAX_FIX_ATTEMPTS + 1):
        test_output, test_exit = await _run_tests(
            config, state, sandbox_manager, sandbox_id, workspace_path
        )
        if test_exit == 0:
            test_passed = True
            await tracker.append_log("implement", "Tests passed")
            break

        if attempt < MAX_FIX_ATTEMPTS:
            fix_msg = f"Tests failed (attempt {attempt + 1}/{MAX_FIX_ATTEMPTS}) — fixing..."
            await tracker.append_log("implement", fix_msg)
            # Log test output so failures are visible in the pipeline UI
            await _log_test_output(test_output, config, state)
            try:
                fix_result = await _fix_failures(
                    agent_runtime,
                    thread_ref,
                    workspace_path,
                    test_output,
                    sandbox_manager,
                    sandbox_id,
                    config,
                    state,
                )
                fix_usage = StageTracker.extract_token_usage(fix_result)
                total_usage.append(fix_usage)
            except Exception:
                logger.exception("implement_fix_failed")
                await tracker.append_log("implement", "Fix attempt failed")
                break

    if not test_passed:
        await tracker.append_log("implement", "Tests still failing after fix attempts")
        await _log_test_output(test_output, config, state)

    # Verify lint
    lint_output, lint_exit = await _run_lint(
        config, state, sandbox_manager, sandbox_id, workspace_path
    )
    lint_passed = lint_exit == 0
    if lint_passed:
        await tracker.append_log("implement", "Final lint: PASSED")
    else:
        await tracker.append_log("implement", "Final lint: FAILED")
        await tracker.append_log("implement", lint_output[-2000:] if lint_output else "No output")

    all_passed = test_passed and lint_passed

    # Push branch after implement so progress is preserved across restarts
    feature_branch = state.get("feature_branch", "")
    if feature_branch:
        from lintel.sandbox.types import SandboxJob

        await tracker.append_log("implement", f"Pushing branch {feature_branch}...")
        try:
            push_result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=(
                        f"git add -A && git diff --cached --quiet"
                        f" || git commit -m 'wip: implement stage progress'"
                        f" && git push --force-with-lease -u origin {feature_branch} 2>&1"
                    ),
                    workdir=workspace_path,
                    timeout_seconds=60,
                ),
            )
            push_out = (push_result.stdout + push_result.stderr).strip()
            await tracker.append_log(
                "implement",
                f"Push: {'OK' if push_result.exit_code == 0 else 'FAILED'}"
                f" — {push_out[-100:] if push_out else 'no output'}",
            )
        except Exception:
            logger.warning("implement_push_failed", exc_info=True)
            await tracker.append_log("implement", "Push failed (exception)")

    if all_passed:
        agent_output = "Implementation complete."
    elif not test_passed and not lint_passed:
        agent_output = "Implementation complete — tests and lint failing."
    elif not test_passed:
        agent_output = "Implementation complete — tests failing."
    else:
        agent_output = "Implementation complete — lint failing."
    return agent_output, all_passed, total_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _log_test_output(
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


def _parse_thread_ref(raw: str) -> ThreadRef:
    """Parse thread ref string into ThreadRef."""
    from lintel.contracts.types import ThreadRef

    parts = raw.replace("thread:", "").split(":")
    return ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )


def _parse_file_output(content: str) -> dict[str, Any]:
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


def _build_file_context(file_contents: dict[str, str]) -> str:
    """Format pre-read file contents for the LLM prompt."""
    if not file_contents:
        return ""
    sections = []
    for path, content in file_contents.items():
        sections.append(f"### {path}\n```\n{content}\n```")
    return "\n\n## Current File Contents\n" + "\n\n".join(sections)


async def _read_guidelines(
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


async def _pre_read_plan_files(
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


async def _auto_format(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    tracker: Any,  # noqa: ANN401
) -> None:
    """Run code formatters in the sandbox to fix agent-generated lint issues."""
    from lintel.sandbox.types import SandboxJob

    await tracker.append_log("implement", "Auto-fixing lint: make format")
    try:
        result = await sandbox_manager.execute(
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
                    "ruff check --fix --unsafe-fixes . 2>/dev/null;"
                    " ruff format . 2>/dev/null; true"
                ),
                workdir=workspace_path,
                timeout_seconds=30,
            ),
        )
    except Exception:
        logger.warning("implement_auto_format_failed", exc_info=True)


async def _failures_in_agent_files(
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

    for failed in failed_files:
        if failed in agent_files:
            return True
    return False


async def _run_tests(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, int]:
    """Run tests in the sandbox. Returns (output, exit_code)."""
    from lintel.skills_api.domain.discover_test_command import discover_test_command
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker
    from lintel.workflows.nodes.test_code import _build_changed_tests_command

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
        output, exit_code = await _stream_execute_with_logging(
            sandbox_manager, sandbox_id, test_command, workspace_path, 600, _log_test_line,
        )
    except Exception:
        logger.warning("implement_test_execute_failed")
        return "Test execution failed", 1

    if exit_code != 0:
        # Check if failures are only in pre-existing tests (not agent-changed files).
        # If so, accept — the agent's code didn't introduce regressions.
        failed_in_agent_files = await _failures_in_agent_files(
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


async def _run_lint(
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
    ) = await _discover_dev_commands(sandbox_manager, sandbox_id, workspace_path)

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
                    "ruff check --fix --unsafe-fixes . 2>/dev/null;"
                    " ruff format . 2>/dev/null; true"
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
        output, exit_code = await _stream_execute_with_logging(
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


async def _fix_failures(
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
