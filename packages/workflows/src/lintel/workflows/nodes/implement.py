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

from typing import TYPE_CHECKING, Any

import structlog

# Re-export prompt constants so callers that previously imported them from this
# module continue to work without changes.
from lintel.workflows.nodes._impl_discovery import FIX_SYSTEM_PROMPT as FIX_SYSTEM_PROMPT
from lintel.workflows.nodes._impl_structured import GENERATE_SYSTEM_PROMPT as GENERATE_SYSTEM_PROMPT
from lintel.workflows.nodes._impl_tdd import TDD_SYSTEM_PROMPT as TDD_SYSTEM_PROMPT

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

MAX_NODE_FIX_ATTEMPTS = 2

# Patterns that indicate a generic / placeholder work item title (case-insensitive).
_GENERIC_TITLE_PATTERNS = (
    "lintel: implement feature",
    "implement feature",
    "audit and harden",
    "lintel: audit",
    "new feature",
    "feature request",
    "todo",
    "fix bug",
    "untitled",
)

MIN_DESCRIPTION_LENGTH = 20


def _validate_work_item(state: Mapping[str, Any]) -> str | None:
    """Validate that state contains a usable work item.

    Returns an error string if validation fails, or ``None`` if the work item
    is acceptable.

    The pipeline stores work item data in two ways:
    - ``work_item_id`` + ``work_item_title`` (ThreadWorkflowState fields)
    - ``work_item`` dict (test fixtures and direct invocations)
    Both are accepted.
    """
    # Try the canonical state fields first (ThreadWorkflowState)
    title: str = (state.get("work_item_title") or "").strip()
    work_item_id: str = (state.get("work_item_id") or "").strip()

    # Fall back to work_item dict (used by tests and direct invocations)
    work_item = state.get("work_item")
    if not title and work_item:
        if isinstance(work_item, dict):
            title = (work_item.get("title", "") or "").strip()
            work_item_id = work_item_id or (work_item.get("id", "") or "").strip()
        else:
            title = (getattr(work_item, "title", "") or "").strip()
            work_item_id = work_item_id or (getattr(work_item, "id", "") or "").strip()

    if not title and not work_item_id and not work_item:
        return "No work item found in workflow state — cannot proceed with implementation."

    if not title:
        return "Work item has no title — cannot proceed with implementation."

    title_lower = title.lower()
    for pattern in _GENERIC_TITLE_PATTERNS:
        if title_lower == pattern or title_lower.startswith(pattern + " "):
            return (
                f"Work item title is too generic ({title!r}). "
                "Please provide a specific, descriptive title before running the implement stage."
            )

    # Description check: only enforce when work_item dict is present (has description).
    # The ThreadWorkflowState only stores work_item_title, not description.
    description: str = ""
    if work_item:
        if isinstance(work_item, dict):
            description = (work_item.get("description", "") or "").strip()
        else:
            description = (getattr(work_item, "description", "") or "").strip()

    if description and len(description) < MIN_DESCRIPTION_LENGTH:
        return (
            f"Work item description is too short ({len(description)} chars — "
            f"minimum {MIN_DESCRIPTION_LENGTH}). "
            "Please add a detailed description before running the implement stage."
        )

    return None


async def spawn_implementation(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Generate code, write files, run tests, fix until green."""
    from lintel.workflows.nodes._impl_discovery import pre_read_plan_files, read_guidelines
    from lintel.workflows.nodes._impl_structured import implement_structured
    from lintel.workflows.nodes._impl_tdd import implement_tdd
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

    # --- Work item validation guard ---
    validation_error = _validate_work_item(state)
    if validation_error:
        logger.warning("implement_work_item_invalid", reason=validation_error)
        await tracker.mark_running("implement")
        await tracker.append_log("implement", f"Validation failed: {validation_error}")
        await tracker.mark_completed("implement", error=validation_error)
        return {"error": validation_error, "current_phase": "closed"}

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
    workspace_paths: tuple[tuple[str, str], ...] = state.get("workspace_paths", ())

    # Read project guidelines from all repos
    guidelines_parts: list[str] = []
    if workspace_paths and len(workspace_paths) > 1:
        for ws_url, ws_path in workspace_paths:
            label = ws_url.rstrip("/").rsplit("/", 1)[-1] if ws_url else ws_path
            g = await read_guidelines(sandbox_manager, sandbox_id, ws_path)
            if g:
                guidelines_parts.append(f"### {label}\n{g}")
        guidelines = "\n\n".join(guidelines_parts)
    else:
        guidelines = await read_guidelines(sandbox_manager, sandbox_id, workspace_path)

    # Guided context injection from codebase index
    guided_context_section = ""
    project_id = state.get("project_id", "")
    index_store = _configurable.get("codebase_index_store")
    if index_store is None:
        _app = _configurable.get("app_state")
        if _app is None and run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state as _get_app

            _app = _get_app(run_id)
        if _app is not None:
            index_store = getattr(_app, "codebase_index_store", None)
    if index_store is not None and project_id:
        try:
            from lintel.context_injection import ContextInjector

            injector = ContextInjector(index_store)
            desc_parts = messages or []
            description = "\n".join(desc_parts) if desc_parts else ""
            if description:
                from lintel.context_injection.types import ContextBudget

                ctx = await injector.gather_context(
                    project_id, description, budget=ContextBudget(max_tokens=6000)
                )
                guided_context_section = ctx.as_prompt_section
                if guided_context_section:
                    await tracker.append_log(
                        "implement",
                        f"Injected {len(ctx.snippets)} snippet(s) from codebase index",
                    )
                    guided_context_section = (
                        f"\n\n## Guided Context (from codebase index)\n{guided_context_section}"
                    )
        except Exception:
            logger.warning("implement_context_injection_failed", exc_info=True)

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
    file_contents = await pre_read_plan_files(
        sandbox_manager, sandbox_id, workspace_path, all_file_paths
    )
    if file_contents:
        await tracker.append_log("implement", f"Pre-read {len(file_contents)} file(s) from plan")

    file_context = _build_file_context(file_contents)
    research_context = state.get("research_context", "")
    research_section = f"\n\n## Research Context\n{research_context}" if research_context else ""
    guidelines_section = f"\n\n## Project Guidelines\n{guidelines}" if guidelines else ""

    # Inject CLAUDE.md conventions from the target repository
    project_conventions = state.get("project_conventions", "")
    conventions_section = (
        f"\n\n## Project Conventions (from CLAUDE.md)\n{project_conventions}"
        if project_conventions
        else ""
    )

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

    # Multi-repo workspace info for the LLM
    multi_repo_section = ""
    if workspace_paths and len(workspace_paths) > 1:
        repo_lines = []
        for url, ws_path in workspace_paths:
            label = url.rstrip("/").rsplit("/", 1)[-1] if url else ws_path
            repo_lines.append(f"- **{label}**: `{ws_path}`")
        multi_repo_section = (
            "\n\n## Multi-Repository Project\n"
            "This project spans multiple repositories cloned into the sandbox:\n"
            + "\n".join(repo_lines)
            + f"\n\nPrimary repo (feature branch): `{workspace_path}`\n"
            "You may need to read or modify files across repositories.\n"
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
        f"{conventions_section}"
        f"{guided_context_section}"
        f"{multi_repo_section}{review_section}{failure_section}"
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
            agent_output, test_passed, total_usage = await implement_tdd(
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
            agent_output, test_passed, total_usage = await implement_structured(
                agent_runtime=agent_runtime,
                thread_ref=thread_ref,
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
                workspace_path=workspace_path,
                user_prompt=user_prompt,
                config=_config,
                state=state,
            )

        # ---- Node-level fix loop on test failure ----
        # If the strategy exhausted its own retries and tests still fail,
        # run a focused fix cycle: capture test output → agent fix → re-test.
        if not test_passed:
            from lintel.workflows.nodes._impl_discovery import (
                fix_failures,
                log_test_output,
                run_tests,
            )

            for fix_attempt in range(1, MAX_NODE_FIX_ATTEMPTS + 1):
                await tracker.append_log(
                    "implement",
                    f"Node fix attempt {fix_attempt}/{MAX_NODE_FIX_ATTEMPTS}"
                    " — capturing test output for agent",
                )
                test_output, test_exit = await run_tests(
                    _config, state, sandbox_manager, sandbox_id, workspace_path
                )
                if test_exit == 0:
                    test_passed = True
                    await tracker.append_log("implement", "Tests passed after re-run")
                    break

                await log_test_output(test_output, _config, state)

                try:
                    fix_result = await fix_failures(
                        agent_runtime,
                        thread_ref,
                        workspace_path,
                        test_output,
                        sandbox_manager,
                        sandbox_id,
                        _config,
                        state,
                    )
                    fix_usage = tracker.extract_token_usage(fix_result)
                    total_usage.append(fix_usage)
                except Exception:
                    logger.exception("implement_node_fix_failed", attempt=fix_attempt)
                    await tracker.append_log(
                        "implement", f"Fix attempt {fix_attempt} failed (exception)"
                    )
                    break

                # Re-test after fix
                retest_output, retest_exit = await run_tests(
                    _config, state, sandbox_manager, sandbox_id, workspace_path
                )
                if retest_exit == 0:
                    test_passed = True
                    await tracker.append_log(
                        "implement",
                        f"Tests passed after node fix attempt {fix_attempt}",
                    )
                    break

                await tracker.append_log(
                    "implement",
                    f"Tests still failing after node fix attempt {fix_attempt}",
                )
                await log_test_output(retest_output, _config, state)

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
            rebase_result = await git_ops.rebase_on_upstream(base_branch, workdir=workspace_path)
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

    # Persist TestResult entity
    if agent_runtime is not None:
        test_result_store = _configurable.get("test_result_store")
        if test_result_store is None:
            _app = _configurable.get("app_state")
            if _app is None and run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                _app = get_app_state(run_id)
            if _app is not None:
                test_result_store = getattr(_app, "test_result_store", None)
        if test_result_store is not None:
            from uuid import uuid4

            from lintel.domain.types import TestResult, TestVerdict

            test_verdict_enum = TestVerdict.PASSED if test_passed else TestVerdict.FAILED
            test_result = TestResult(
                result_id=str(uuid4()),
                run_id=state.get("run_id", ""),
                stage_id="implement",
                verdict=test_verdict_enum,
            )
            try:
                await test_result_store.add(test_result)
                logger.info("test_result_stored", result_id=test_result.result_id)
            except Exception:
                logger.warning("test_result_persist_failed", exc_info=True)

    # Persist code artifact
    diff_text = artifacts.get("content", "") if isinstance(artifacts, dict) else ""
    if diff_text:
        code_artifact_store = _configurable.get("code_artifact_store")
        if code_artifact_store is None:
            _app = _configurable.get("app_state")
            if _app is None and run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                _app = get_app_state(run_id)
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
    has_test_failure = agent_runtime is not None and not test_passed
    if has_test_failure:
        await tracker.mark_completed(
            "implement", outputs=stage_outputs or None, error="Tests failed"
        )
    else:
        await tracker.mark_completed("implement", outputs=stage_outputs or None)

    # Signal failure through the workflow state so _check_phase routes to close
    # instead of continuing to review/raise_pr with broken code.
    result_dict: dict[str, Any] = {
        "current_phase": "reviewing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
    if has_test_failure:
        result_dict["error"] = "Tests failed after all fix attempts"
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

    Delegates to the canonical implementation in ``_impl_discovery``.
    Kept here for any callers that import it from this module.
    """
    from lintel.workflows.nodes._impl_discovery import stream_execute_with_logging

    return await stream_execute_with_logging(
        sandbox_manager, sandbox_id, command, workdir, timeout_seconds, log_fn
    )


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
# Private helpers used only by spawn_implementation
# ---------------------------------------------------------------------------


def _parse_thread_ref(raw: str) -> ThreadRef:
    """Parse thread ref string into ThreadRef."""
    from lintel.contracts.types import ThreadRef

    parts = raw.replace("thread:", "").split(":")
    return ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )


def _build_file_context(file_contents: dict[str, str]) -> str:
    """Format pre-read file contents for the LLM prompt."""
    if not file_contents:
        return ""
    sections = []
    for path, content in file_contents.items():
        sections.append(f"### {path}\n```\n{content}\n```")
    return "\n\n## Current File Contents\n" + "\n\n".join(sections)
