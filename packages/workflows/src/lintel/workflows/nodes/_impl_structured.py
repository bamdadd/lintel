"""Structured implementation strategy — LiteLLM providers (JSON generation + test/fix loop)."""

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


async def implement_structured(
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
    from lintel.workflows.nodes._impl_discovery import (
        fix_failures,
        log_test_output,
        parse_file_output,
        run_lint,
        run_tests,
    )
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

        files_to_write = parse_file_output(gen_content)
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
    test_output = ""
    for attempt in range(MAX_FIX_ATTEMPTS + 1):
        test_output, test_exit = await run_tests(
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
            await log_test_output(test_output, config, state)
            try:
                fix_result = await fix_failures(
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
        await log_test_output(test_output, config, state)

    # Verify lint
    lint_output, lint_exit = await run_lint(
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
            commit_cmd = (
                "git add -A && git diff --cached --quiet"
                " || git commit -m 'wip: implement stage progress'"
            )
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command=commit_cmd, workdir=workspace_path, timeout_seconds=30),
            )
            # Retry push — force-with-lease can fail on stale refs
            push_result = None
            for push_attempt in range(3):
                if push_attempt > 0:
                    await sandbox_manager.execute(
                        sandbox_id,
                        SandboxJob(
                            command="git fetch origin 2>&1 || true",
                            workdir=workspace_path,
                            timeout_seconds=30,
                        ),
                    )
                push_result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(
                        command=(f"git push --force-with-lease -u origin {feature_branch} 2>&1"),
                        workdir=workspace_path,
                        timeout_seconds=60,
                    ),
                )
                if push_result.exit_code == 0:
                    break
                push_out = (push_result.stdout + push_result.stderr).strip()
                if "stale info" not in push_out:
                    break
            # Fallback to force push if force-with-lease keeps failing
            if push_result and push_result.exit_code != 0:
                push_result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(
                        command=f"git push --force -u origin {feature_branch} 2>&1",
                        workdir=workspace_path,
                        timeout_seconds=60,
                    ),
                )
            push_out = (push_result.stdout + push_result.stderr).strip() if push_result else ""
            await tracker.append_log(
                "implement",
                f"Push: {'OK' if push_result and push_result.exit_code == 0 else 'FAILED'}"
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
