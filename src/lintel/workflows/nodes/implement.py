"""Implementation workflow node — runs coder agent with sandbox tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)

IMPLEMENT_SYSTEM_PROMPT = """\
You are a senior software engineer implementing a feature in a codebase.
You have access to a sandbox with the project cloned at the workspace path provided below.

You will be given a plan with tasks. Implement each task by:
1. Reading relevant files to understand the code
2. Writing or modifying files to implement the change
3. Running tests to verify your changes

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

    await mark_running(_config, "implement", state)
    await append_log(_config, "implement", "Starting implementation node", state)

    if sandbox_manager is None:
        await mark_completed(_config, "implement", state, error="No sandbox manager available")
        return {
            "error": "No sandbox manager available",
            "current_phase": "closed",
        }

    logger.info(
        "implementation_started phase=implementing thread_ref=%s",
        state.get("thread_ref", ""),
    )

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        await mark_completed(_config, "implement", state, error="No sandbox available")
        return {
            "error": "No sandbox available — setup_workspace must run first",
            "current_phase": "closed",
        }

    plan = state.get("plan", {})
    messages = state.get("sanitized_messages", [])

    # Build the implementation prompt from plan
    tasks = plan.get("tasks", [])
    task_text = "\n".join(
        f"- {t}" if isinstance(t, str) else f"- {t.get('title', t)}" for t in tasks
    )
    plan_summary = plan.get("summary", "Implement the requested feature.")

    user_prompt = (
        f"## Plan\n{plan_summary}\n\n## Tasks\n{task_text}\n\n"
        f"## Original request\n{chr(10).join(messages)}"
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

            result = await agent_runtime.execute_step(
                thread_ref=thread_ref,
                agent_role=AgentRole.CODER,
                step_name="implement",
                messages=[
                    {"role": "system", "content": IMPLEMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                tools=sandbox_tool_schemas(),
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
            )
            agent_output = result.get("content", "Implementation complete.")
            usage = extract_token_usage("implement", result)
            await append_log(_config, "implement", "Agent completed", state)
        except Exception:
            logger.exception("agent_implementation_failed")
            await append_log(_config, "implement", "Agent implementation failed", state)
            agent_output = "Agent implementation failed — collecting partial artifacts."
    else:
        # No agent runtime: execute plan tasks as shell commands if possible
        agent_output = "No agent runtime configured — sandbox artifacts collected."

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
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id)
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
    diff_text = artifacts.get("diff", "") if isinstance(artifacts, dict) else ""
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
    await mark_completed(_config, "implement", state, outputs=stage_outputs or None)

    result_dict: dict[str, Any] = {
        "current_phase": "testing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
    if usage:
        result_dict["token_usage"] = [usage]
    return result_dict
