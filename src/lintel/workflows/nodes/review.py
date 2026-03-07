"""Review node: runs code review agent on implementation artifacts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """\
You are a senior code reviewer. Review the following git diff for:
1. Correctness — does the code do what it should?
2. Security — any vulnerabilities (injection, secrets, etc.)?
3. Quality — clean code, naming, structure?
4. Tests — are changes covered by tests?

Provide a concise review with:
- VERDICT: APPROVE or REQUEST_CHANGES
- Summary of findings
- Specific issues (if any)
"""


async def review_output(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
    *,
    sandbox_manager: SandboxManager | None = None,
    agent_runtime: AgentRuntime | None = None,
) -> dict[str, Any]:
    """Review implementation artifacts using the reviewer agent."""
    from lintel.contracts.types import AgentRole, SandboxJob, ThreadRef
    from lintel.workflows.nodes._stage_tracking import mark_completed, mark_running

    _config = config or {}
    await mark_running(_config, "review", state)

    sandbox_id = state.get("sandbox_id")
    diff_text = ""

    # Get the diff from the sandbox
    if sandbox_id and sandbox_manager is not None:
        try:
            result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="git diff HEAD", workdir="/workspace/repo", timeout_seconds=30),
            )
            diff_text = result.stdout
        except Exception:
            logger.warning("review_diff_collection_failed")

    # Fall back to collected artifacts
    if not diff_text:
        for sr in state.get("sandbox_results", []):
            if isinstance(sr, dict) and sr.get("diff"):
                diff_text = sr["diff"]
                break

    if not diff_text:
        await mark_completed(_config, "review", state)
        return {
            "current_phase": "awaiting_merge_approval",
            "pending_approvals": ["merge_approval"],
            "agent_outputs": [
                {"node": "review", "verdict": "approve", "output": "No changes to review."}
            ],
        }

    # Truncate very large diffs
    if len(diff_text) > 10000:
        diff_text = diff_text[:10000] + "\n... (diff truncated)"

    review_output_text = ""
    if agent_runtime is not None:
        thread_ref_str = state["thread_ref"]
        parts = thread_ref_str.replace("thread:", "").split(":")
        thread_ref = ThreadRef(
            workspace_id=parts[0] if len(parts) > 0 else "",
            channel_id=parts[1] if len(parts) > 1 else "",
            thread_ts=parts[2] if len(parts) > 2 else "",
        )
        try:
            result = await agent_runtime.execute_step(
                thread_ref=thread_ref,
                agent_role=AgentRole.REVIEWER,
                step_name="review",
                messages=[
                    {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": f"```diff\n{diff_text}\n```"},
                ],
            )
            review_output_text = result.get("content", "Review complete.")
        except Exception:
            logger.exception("agent_review_failed")
            review_output_text = "Agent review failed — defaulting to manual review."
    else:
        review_output_text = "No agent runtime configured — manual review required."

    # Parse verdict from review output
    verdict = "request_changes"
    upper_text = review_output_text.upper()
    if "APPROVE" in upper_text and "REQUEST_CHANGES" not in upper_text:
        verdict = "approve"

    await mark_completed(_config, "review", state)
    return {
        "current_phase": "awaiting_merge_approval",
        "pending_approvals": ["merge_approval"],
        "agent_outputs": [
            {"node": "review", "verdict": verdict, "output": review_output_text}
        ],
    }
