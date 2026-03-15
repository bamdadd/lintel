"""TDD implementation strategy — Claude models (Claude Code, Bedrock, Anthropic API)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

MAX_TDD_FIX_ATTEMPTS = 2

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


async def implement_tdd(
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
    from lintel.workflows.nodes._impl_discovery import (
        auto_format,
        discover_dev_commands,
        load_skill_system_prompt,
        log_test_output,
        run_lint,
        run_tests,
    )
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.append_log("implement", "Using TDD mode (Claude model)")

    # Discover test/lint commands for the project
    (
        test_command,
        lint_command,
        typecheck_command,
        test_single_command,
    ) = await discover_dev_commands(sandbox_manager, sandbox_id, workspace_path)

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
    system_prompt = await load_skill_system_prompt(
        config,
        state,
        skill_id,
        workspace_path,
        fallback_template=TDD_SYSTEM_PROMPT,
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
    await auto_format(sandbox_manager, sandbox_id, workspace_path, tracker)

    # Test/fix loop — give the LLM a chance to fix failures
    test_passed = False
    test_output = ""
    for attempt in range(MAX_TDD_FIX_ATTEMPTS + 1):
        test_output, test_exit = await run_tests(
            config, state, sandbox_manager, sandbox_id, workspace_path
        )
        if test_exit == 0:
            test_passed = True
            await tracker.append_log("implement", "Tests: PASSED")
            break

        if attempt < MAX_TDD_FIX_ATTEMPTS:
            msg = f"Tests failed (attempt {attempt + 1}/{MAX_TDD_FIX_ATTEMPTS}) — fixing..."
            await tracker.append_log("implement", msg)
            await log_test_output(test_output, config, state)
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
            await auto_format(sandbox_manager, sandbox_id, workspace_path, tracker)

    if not test_passed:
        await tracker.append_log("implement", "Tests still failing after fix attempts")
        await log_test_output(test_output, config, state)

    # Verify lint
    lint_output, lint_exit = await run_lint(
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
