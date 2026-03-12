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
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.protocols import SandboxManager
    from lintel.contracts.types import ThreadRef
    from lintel.contracts.workflow_models import AgentStepResult
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

MAX_FIX_ATTEMPTS = 3

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

## Lint & Type Check
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
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        mark_completed,
        mark_running,
    )

    _config = config or {}
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

    await mark_running(_config, "implement", state)
    await append_log(_config, "implement", "Starting implementation", state)

    if sandbox_manager is None:
        await mark_completed(_config, "implement", state, error="No sandbox manager available")
        return {"error": "No sandbox manager available", "current_phase": "closed"}

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        await mark_completed(_config, "implement", state, error="No sandbox available")
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
    workspace_path = state.get("workspace_path", "/workspace/repo")

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
        await append_log(
            _config, "implement", f"Pre-read {len(file_contents)} file(s) from plan", state
        )

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

    user_prompt = (
        f"## Plan\n{plan_summary}\n\n## Tasks\n{task_text}\n\n"
        f"## Original request\n{chr(10).join(messages)}"
        f"{file_context}{research_section}{guidelines_section}{review_section}"
    )

    # Parse thread ref
    thread_ref = _parse_thread_ref(state["thread_ref"])

    from lintel.contracts.workflow_models import TokenUsage

    total_usage: list[TokenUsage] = []
    agent_output = "No agent runtime configured."

    if agent_runtime is not None:
        # Detect provider to choose execution strategy
        is_claude_code, _provider, _model_name = await _resolve_coder_policy(agent_runtime)

        from lintel.workflows.nodes._stage_tracking import log_llm_context

        await log_llm_context(_config, "implement", "coder", "implement_generate", state)

        if is_claude_code:
            # ---- Claude Code TDD path ----
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
        from lintel.workflows.nodes._git_helpers import rebase_on_upstream

        try:
            rebase_result = await rebase_on_upstream(sandbox_manager, sandbox_id, base_branch)
            if not rebase_result.success:
                rebase_warning = rebase_result.message
        except Exception:
            logger.warning("implement_rebase_failed", exc_info=True)
            rebase_warning = "Rebase failed — sandbox may be unavailable"

    # Collect artifacts
    await append_log(_config, "implement", "Collecting artifacts...", state)
    try:
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id, workdir=workspace_path)
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        await mark_completed(_config, "implement", state, error="Failed to collect artifacts")
        return await handle_node_error(state, "implement", Exception("Failed to collect artifacts"))

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
        if code_artifact_store is not None:
            from uuid import uuid4

            from lintel.contracts.types import CodeArtifact

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
            except Exception:
                logger.warning("code_artifact_persist_failed")

    stage_outputs: dict[str, object] = {}
    if total_usage:
        # Merge usage across generate + fix attempts
        merged = TokenUsage(
            step="implement",
            input_tokens=sum(u.input_tokens for u in total_usage),
            output_tokens=sum(u.output_tokens for u in total_usage),
        )
        stage_outputs["token_usage"] = merged.model_dump()
    if diff_text:
        stage_outputs["diff"] = diff_text[:50000]
    if agent_runtime is not None and not test_passed:
        await mark_completed(
            _config, "implement", state, outputs=stage_outputs or None, error="Tests failed"
        )
    else:
        await mark_completed(_config, "implement", state, outputs=stage_outputs or None)

    result_dict: dict[str, Any] = {
        "current_phase": "reviewing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
    if total_usage:
        result_dict["token_usage"] = [u.model_dump() for u in total_usage]
    return result_dict


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


async def _resolve_coder_policy(
    agent_runtime: AgentRuntime,
) -> tuple[bool, str, str]:
    """Resolve the coder role's model policy.

    Returns (is_claude_code, provider, model_name).
    """
    from lintel.contracts.types import AgentRole

    try:
        policy = await agent_runtime._model_router.select_model(
            AgentRole.CODER, "implement_generate"
        )
        return policy.provider == "claude_code", policy.provider, policy.model_name
    except Exception:
        return False, "unknown", "unknown"


async def _is_claude_code_provider(agent_runtime: AgentRuntime) -> bool:
    """Check if the coder role is assigned to Claude Code provider."""
    is_cc, _, _ = await _resolve_coder_policy(agent_runtime)
    return is_cc


# ---------------------------------------------------------------------------
# TDD path (Claude Code)
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
) -> tuple[str, bool, list[TokenUsage]]:
    """Run implementation via Claude Code with TDD system prompt.

    Returns (agent_output, test_passed, total_usage).
    """
    from lintel.contracts.types import AgentRole
    from lintel.contracts.workflow_models import TokenUsage
    from lintel.workflows.nodes._stage_tracking import append_log, extract_token_usage

    await append_log(config, "implement", "Using Claude Code TDD mode", state)

    # Discover test/lint commands for the project
    (
        test_command,
        lint_command,
        typecheck_command,
        test_single_command,
    ) = await _discover_dev_commands(sandbox_manager, sandbox_id, workspace_path)

    await append_log(config, "implement", f"Test: {test_command[:60]}", state)
    await append_log(config, "implement", f"Lint: {lint_command[:60]}", state)

    # Install deps first
    from lintel.skills.discover_test_command import discover_test_command

    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workspace_path)
        from lintel.contracts.types import SandboxJob

        for cmd in discovery.setup_commands:
            await append_log(config, "implement", f"Setup: {cmd[:60]}", state)
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command=cmd, workdir=workspace_path, timeout_seconds=180),
            )
    except Exception:
        logger.warning("implement_tdd_setup_failed")

    # Configure git for commits inside sandbox
    from lintel.contracts.types import SandboxJob

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
    await append_log(config, "implement", f"Skill: {skill_id} (TDD)", state)

    await append_log(config, "implement", "Starting TDD implementation...", state)

    async def _on_activity(activity: str) -> None:
        if activity:
            await append_log(config, "implement", activity, state)

    try:
        result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="implement_generate",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            sandbox_manager=sandbox_manager,
            sandbox_id=sandbox_id,
            on_activity=_on_activity,
        )
        usage = extract_token_usage("implement_tdd", result)
        content = result.content
        await append_log(
            config, "implement", f"TDD session complete ({len(content):,} chars)", state
        )
    except Exception:
        logger.exception("implement_tdd_failed")
        await append_log(config, "implement", "TDD session failed", state)
        return "Implementation failed.", False, []

    # Verify final test state
    test_output, test_exit = await _run_tests(
        config, state, sandbox_manager, sandbox_id, workspace_path
    )
    test_passed = test_exit == 0
    if test_passed:
        await append_log(config, "implement", "Final tests: PASSED", state)
    else:
        await append_log(config, "implement", "Final tests: FAILED", state)
        # Log the test output so failures are visible in the pipeline UI
        await _log_test_output(test_output, config, state)

    agent_output = (
        "Implementation complete." if test_passed else "Implementation complete — tests failing."
    )
    return agent_output, test_passed, [usage]


async def _discover_dev_commands(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, str, str, str]:
    """Discover test, lint, typecheck, and single-test commands.

    Returns (test_command, lint_command, typecheck_command, test_single_command).
    """
    from lintel.contracts.types import SandboxJob

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

    # Detect project type
    detect = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"ls {workspace_path}/pyproject.toml {workspace_path}/package.json 2>/dev/null",
            workdir=workspace_path,
            timeout_seconds=5,
        ),
    )
    files = detect.stdout

    # Defaults
    test_command = "make test-unit" if "test-unit:" in makefile else "make test"
    lint_command = "make lint" if "lint:" in makefile else "echo 'no lint configured'"
    typecheck_command = "make typecheck" if "typecheck:" in makefile else "echo 'no typecheck'"
    test_single_command = "uv run pytest <file> -v"

    if "pyproject.toml" in files:
        if "test-unit:" not in makefile:
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
) -> tuple[str, bool, list[TokenUsage]]:
    """Run implementation via structured JSON generation + test + fix loop.

    Returns (agent_output, test_passed, total_usage).
    """
    from lintel.contracts.types import AgentRole
    from lintel.contracts.workflow_models import TokenUsage
    from lintel.workflows.nodes._stage_tracking import append_log, extract_token_usage

    total_usage: list[TokenUsage] = []

    await append_log(config, "implement", "Skill: structured-generate (JSON)", state)

    # --- Phase 1: Generate code (single LLM call, no tools) ---
    await append_log(config, "implement", "Generating code...", state)
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
        )
        gen_content = gen_result.content
        usage = extract_token_usage("implement_generate", gen_result)
        total_usage.append(usage)

        files_to_write = _parse_file_output(gen_content)
        if not files_to_write:
            await append_log(config, "implement", "No files generated — fallback to tools", state)
            files_to_write = {}
    except Exception:
        logger.exception("implement_generate_failed")
        await append_log(config, "implement", "Code generation failed", state)
        files_to_write = {}

    # --- Phase 2: Write files to sandbox ---
    if files_to_write:
        await append_log(config, "implement", f"Writing {len(files_to_write)} file(s)", state)
        for rel_path, content in files_to_write.items():
            abs_path = f"{workspace_path}/{rel_path}" if not rel_path.startswith("/") else rel_path
            try:
                await sandbox_manager.write_file(sandbox_id, abs_path, content)
                lines = content.count("\n") + 1
                fname = rel_path.split("/")[-1]
                await append_log(config, "implement", f"  wrote {fname} ({lines} lines)", state)
            except Exception:
                logger.warning("implement_write_failed", path=rel_path)
                await append_log(config, "implement", f"  FAILED: {rel_path}", state)

    # --- Phase 3: Run tests, fix if broken ---
    test_passed = False
    for attempt in range(MAX_FIX_ATTEMPTS + 1):
        test_output, test_exit = await _run_tests(
            config, state, sandbox_manager, sandbox_id, workspace_path
        )
        if test_exit == 0:
            test_passed = True
            await append_log(config, "implement", "Tests passed", state)
            break

        if attempt < MAX_FIX_ATTEMPTS:
            await append_log(
                config,
                "implement",
                f"Tests failed (attempt {attempt + 1}/{MAX_FIX_ATTEMPTS}) — fixing...",
                state,
            )
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
                fix_usage = extract_token_usage("implement_fix", fix_result)
                total_usage.append(fix_usage)
            except Exception:
                logger.exception("implement_fix_failed")
                await append_log(config, "implement", "Fix attempt failed", state)
                break

    if not test_passed:
        await append_log(config, "implement", "Tests still failing after fix attempts", state)
        await _log_test_output(test_output, config, state)

    agent_output = (
        "Implementation complete." if test_passed else "Implementation complete — tests failing."
    )
    return agent_output, test_passed, total_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _log_test_output(
    test_output: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> None:
    """Log test output to pipeline stage logs, extracting the failure summary."""
    from lintel.workflows.nodes._stage_tracking import append_log

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

    await append_log(config, "implement", f"Test output:\n```\n{summary}\n```", state)


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
    from lintel.contracts.types import SandboxJob

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


async def _run_tests(
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> tuple[str, int]:
    """Run tests in the sandbox. Returns (output, exit_code)."""
    from lintel.contracts.types import SandboxJob
    from lintel.skills.discover_test_command import discover_test_command
    from lintel.workflows.nodes._stage_tracking import append_log
    from lintel.workflows.nodes.test_code import _build_changed_tests_command

    # Discover test command
    try:
        discovery = await discover_test_command(sandbox_manager, sandbox_id, workspace_path)
    except Exception:
        logger.warning("implement_test_discovery_failed")
        return "Test discovery failed", 1

    test_command = discovery.test_command
    setup_commands = discovery.setup_commands

    # Run setup (dep install)
    for cmd in setup_commands:
        await append_log(config, "implement", f"Setup: {cmd[:60]}", state)
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=cmd, workdir=workspace_path, timeout_seconds=180),
        )

    # Try changed tests first
    changed_cmd = await _build_changed_tests_command(sandbox_manager, sandbox_id, workspace_path)
    if changed_cmd:
        test_command = changed_cmd

    await append_log(config, "implement", f"Running tests: {test_command[:80]}", state)
    try:
        result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=test_command, workdir=workspace_path, timeout_seconds=600),
        )
    except Exception:
        logger.warning("implement_test_execute_failed")
        return "Test execution failed", 1

    output = result.stdout + result.stderr
    if len(output) > 5000:
        output = output[:2500] + "\n...(truncated)...\n" + output[-2500:]

    return output, result.exit_code


async def _fix_failures(
    agent_runtime: AgentRuntime,
    thread_ref: ThreadRef,
    workspace_path: str,
    test_output: str,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
) -> AgentStepResult:
    """Give the LLM test failures and let it fix with a focused tool loop."""
    from lintel.agents.sandbox_tools import sandbox_tool_schemas
    from lintel.contracts.types import AgentRole
    from lintel.workflows.nodes._stage_tracking import append_log

    async def _on_tool_call(
        iteration: int,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: str,
    ) -> None:
        short_name = tool_name.replace("sandbox_", "")
        preview = _format_tool_preview(short_name, tool_args, tool_result)
        await append_log(config, "implement", f"  fix [{iteration}] {short_name}: {preview}", state)

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
