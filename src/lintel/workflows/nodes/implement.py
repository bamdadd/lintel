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
You have access to a sandbox with the project cloned at /workspace/repo.

You will be given a plan with tasks. Implement each task by:
1. Reading relevant files to understand the code
2. Writing or modifying files to implement the change
3. Running tests to verify your changes

Work methodically through each task. Write clean, production-quality code.
"""


async def spawn_implementation(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
    *,
    sandbox_manager: SandboxManager,
    agent_runtime: AgentRuntime | None = None,
) -> dict[str, Any]:
    """Run the coder agent with sandbox tools to implement the plan."""
    from lintel.contracts.types import AgentRole, ThreadRef
    from lintel.workflows.nodes._stage_tracking import mark_completed, mark_running

    _config = config or {}
    await mark_running(_config, "implement", state)

    logger.info(
        "implementation_started",
        phase="implementing",
        thread_ref=state.get("thread_ref", ""),
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

    if agent_runtime is not None:
        try:
            result = await agent_runtime.execute_step(
                thread_ref=thread_ref,
                agent_role=AgentRole.CODER,
                step_name="implement",
                messages=[
                    {"role": "system", "content": IMPLEMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            agent_output = result.get("content", "Implementation complete.")
        except Exception:
            logger.exception("agent_implementation_failed")
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
            sandbox_manager, sandbox_id, base_branch,
        )
        if not rebase_result["success"]:
            rebase_warning = rebase_result["message"]

    # Collect git diff as artifacts
    try:
        artifacts = await sandbox_manager.collect_artifacts(sandbox_id)
    except Exception:
        from lintel.workflows.nodes._error_handling import handle_node_error

        await mark_completed(_config, "implement", state, error="Failed to collect artifacts")
        return await handle_node_error(
            state, "implement", Exception("Failed to collect artifacts"),
        )

    outputs: list[dict[str, Any]] = [{"node": "implement", "output": agent_output}]
    if rebase_warning:
        outputs.append({"node": "implement_rebase", "output": rebase_warning})

    await mark_completed(_config, "implement", state)
    return {
        "current_phase": "testing",
        "agent_outputs": outputs,
        "sandbox_results": [artifacts],
    }
