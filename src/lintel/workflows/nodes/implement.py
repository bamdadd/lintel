"""Implementation workflow node — runs coder agent with sandbox tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

IMPLEMENT_SYSTEM_PROMPT = """\
You are a senior software engineer implementing a feature in a codebase.
You have access to sandbox tools to read, write, and execute commands.

IMPORTANT: You MUST use the provided tools to make changes. Do NOT just describe \
what to do — actually use sandbox_write_file to write code and sandbox_execute_command \
to run commands.

The workspace is at: {workspace_path}

Follow this workflow:
1. Use sandbox_list_files to explore the workspace directory
2. Use sandbox_read_file to understand existing code
3. Use sandbox_write_file to create or modify files
4. Use sandbox_execute_command to run tests or verify changes

Work methodically through each task. Write clean, production-quality code.
"""


async def spawn_implementation(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Run the coder agent with sandbox tools to implement the plan."""
    from lintel.contracts.types import AgentRole, ThreadRef
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        extract_token_usage,
        mark_completed,
        mark_running,
    )

    _config = config or {}
    _configurable = _config.get("configurable", {})
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    agent_runtime: AgentRuntime | None = _configurable.get("agent_runtime")

    # LangGraph strips custom configurable keys on resume after interrupt.
    # Fall back to the runtime registry which persists across interrupts.
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
        config_keys=list(_configurable.keys()),
    )

    await mark_running(_config, "implement", state)
    await append_log(_config, "implement", "Starting implementation node", state)

    if sandbox_manager is None:
        await mark_completed(_config, "implement", state, error="No sandbox manager available")
        return {
            "error": "No sandbox manager available",
            "current_phase": "closed",
        }

    logger.info(
        "implementation_started",
        thread_ref=state.get("thread_ref", ""),
    )

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        await mark_completed(_config, "implement", state, error="No sandbox available")
        return {
            "error": "No sandbox available — setup_workspace must run first",
            "current_phase": "closed",
        }

    # Reconnect network so the agent can install packages if needed
    try:
        await sandbox_manager.reconnect_network(sandbox_id)
        await append_log(_config, "implement", "Network reconnected for implementation", state)
    except Exception:
        logger.warning("implement_reconnect_network_failed")

    plan = state.get("plan", {})
    messages = state.get("sanitized_messages", [])
    workspace_path = state.get("workspace_path", "/workspace/repo")

    # Read project guidelines for the agent
    guidelines = ""
    for guide_file in ("CLAUDE.md", "docs/agents.md"):
        try:
            from lintel.contracts.types import SandboxJob

            guide_result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=f"cat {workspace_path}/{guide_file} 2>/dev/null || true",
                    workdir=workspace_path,
                    timeout_seconds=10,
                ),
            )
            if guide_result.stdout.strip():
                guidelines += f"\n\n## {guide_file}\n{guide_result.stdout.strip()}"
        except Exception:
            pass

    # Build the implementation prompt from plan
    tasks = plan.get("tasks", [])
    task_text = "\n".join(
        f"- {t}" if isinstance(t, str) else f"- {t.get('title', t)}" for t in tasks
    )
    plan_summary = plan.get("summary", "Implement the requested feature.")

    research_context = state.get("research_context", "")
    research_section = f"\n\n## Research Context\n{research_context}" if research_context else ""

    guidelines_section = f"\n\n## Project Guidelines{guidelines}" if guidelines else ""

    user_prompt = (
        f"## Plan\n{plan_summary}\n\n## Tasks\n{task_text}\n\n"
        f"## Original request\n{chr(10).join(messages)}"
        f"{research_section}"
        f"{guidelines_section}"
    )

    # Parse thread ref for agent runtime
    thread_ref_str = state["thread_ref"]
    parts = thread_ref_str.replace("thread:", "").split(":")
    thread_ref = ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )

    usage: dict[str, Any] | None = None
    if agent_runtime is not None:
        await append_log(_config, "implement", "Invoking coder agent...", state)
        try:
            from lintel.agents.sandbox_tools import sandbox_tool_schemas

            async def _on_tool_call(
                iteration: int,
                tool_name: str,
                tool_result: str,
            ) -> None:
                short_name = tool_name.replace("sandbox_", "")
                preview = tool_result[:120].replace("\n", " ") if tool_result else ""
                await append_log(
                    _config,
                    "implement",
                    f"[{iteration}] {short_name}: {preview}",
                    state,
                )

            result = await agent_runtime.execute_step(
                thread_ref=thread_ref,
                agent_role=AgentRole.CODER,
                step_name="implement",
                messages=[
                    {
                        "role": "system",
                        "content": IMPLEMENT_SYSTEM_PROMPT.format(
                            workspace_path=state.get("workspace_path", "/workspace/repo"),
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                tools=sandbox_tool_schemas(),
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
                max_iterations=50,
                on_tool_call=_on_tool_call,
            )
            agent_output = result.get("content", "Implementation complete.")
            usage = extract_token_usage("implement", result)
            iterations = result.get("tool_iterations", 0)
            await append_log(
                _config,
                "implement",
                f"Agent completed — {iterations} tool iteration(s)",
                state,
            )
        except Exception:
            logger.exception("agent_implementation_failed")
            await append_log(_config, "implement", "Agent implementation failed", state)
            agent_output = "Agent implementation failed — collecting partial artifacts."
    else:
        # No agent runtime: execute plan tasks as shell commands if possible
        agent_output = "No agent runtime configured — sandbox artifacts collected."

    # Disconnect network after implementation
    import contextlib

    with contextlib.suppress(Exception):
        await sandbox_manager.disconnect_network(sandbox_id)

    # Attempt rebase on base branch before collecting artifacts
    rebase_warning = ""
    base_branch = state.get("repo_branch", "main")
    if base_branch:
        from lintel.workflows.nodes._git_helpers import rebase_on_upstream

        rebase_result = await rebase_on_upstream(
            sandbox_manager,
            sandbox_id,
            base_branch,
        )
        if not rebase_result["success"]:
            rebase_warning = rebase_result["message"]

    # Collect git diff as artifacts
    await append_log(_config, "implement", "Collecting artifacts...", state)
    try:
        workspace_path = state.get("workspace_path", "/workspace/repo")
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id, workdir=workspace_path)
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        await mark_completed(_config, "implement", state, error="Failed to collect artifacts")
        return await handle_node_error(
            state,
            "implement",
            Exception("Failed to collect artifacts"),
        )

    outputs: list[dict[str, Any]] = [{"node": "implement", "output": agent_output}]
    if rebase_warning:
        outputs.append({"node": "implement_rebase", "output": rebase_warning})

    # Persist code artifact if diff available
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
                await append_log(_config, "implement", "Code artifact persisted", state)
            except Exception:
                logger.warning("code_artifact_persist_failed")

    stage_outputs: dict[str, object] = {}
    if usage:
        stage_outputs["token_usage"] = usage
    if diff_text:
        # Truncate diff for stage output (full diff is in the artifact)
        stage_outputs["diff"] = diff_text[:50000]
    await mark_completed(_config, "implement", state, outputs=stage_outputs or None)

    result_dict: dict[str, Any] = {
        "current_phase": "testing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
    if usage:
        result_dict["token_usage"] = [usage]
    return result_dict
