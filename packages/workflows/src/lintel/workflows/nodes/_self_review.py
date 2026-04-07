"""Self-review quality loop — proud + world-class checks before lint/test.

Inspired by https://github.com/robertbagge/claude-roadhouse-plugin
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

MAX_SELF_REVIEW_ITERATIONS = 3

PROUD_REVIEW_PROMPT = """\
Are you proud of the work you have done in this session? Anything you would like to change \
here and now?

Review the work carefully. Identify any issues, but do NOT edit any files.

Share your feedback, then output your verdict:

<verdict>needs-work</verdict> — you found issues. Describe what needs to be fixed.
<verdict>roadhouse!</verdict> — you found nothing to change. Describe what makes the work good.
"""

WORLD_CLASS_REVIEW_PROMPT = """\
Would you call the work we have been doing on this branch exquisite? Is it world class? \
If not, what would need to change to make it so?

Review the work carefully. Identify any issues, but do NOT edit any files.

Share your feedback, then output your verdict:

<verdict>needs-work</verdict> — you found issues. Describe what needs to change to make it \
world class.
<verdict>roadhouse!</verdict> — the work is genuinely world class. Describe what makes it \
excellent.
"""

_VERDICT_PATTERN = re.compile(r"<verdict>\s*(.*?)\s*</verdict>", re.IGNORECASE | re.DOTALL)


def _extract_verdict(response: str) -> str:
    """Parse ``<verdict>...</verdict>`` tag from an LLM response.

    Returns ``"roadhouse!"`` or ``"needs-work"``.  Falls back to
    ``"needs-work"`` when the tag is missing or unrecognised.
    """
    match = _VERDICT_PATTERN.search(response)
    if not match:
        return "needs-work"
    raw = match.group(1).strip().lower()
    if raw.startswith("roadhouse"):
        return "roadhouse!"
    return "needs-work"


async def _get_diff(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
) -> str:
    """Return the staged + unstaged diff inside the sandbox."""
    from lintel.sandbox.types import SandboxJob

    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="git diff HEAD 2>/dev/null || git diff 2>/dev/null || echo '(no diff)'",
            workdir=workspace_path,
            timeout_seconds=30,
        ),
    )
    return (result.stdout + result.stderr).strip()


async def run_self_review_loop(
    *,
    agent_runtime: AgentRuntime,
    thread_ref: ThreadRef,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workspace_path: str,
    config: RunnableConfig | dict[str, Any],
    state: ThreadWorkflowState,
    total_usage: list[dict[str, Any]],
) -> None:
    """Run the proud + world-class self-review loop.

    Mutates *total_usage* in place to accumulate token usage from review and
    fix steps.  Writes fixes directly to the sandbox when needed.
    """
    from lintel.agents.types import AgentRole
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)

    for iteration in range(1, MAX_SELF_REVIEW_ITERATIONS + 1):
        diff = await _get_diff(sandbox_manager, sandbox_id, workspace_path)
        await tracker.append_log(
            "implement",
            f"Self-review iteration {iteration}/{MAX_SELF_REVIEW_ITERATIONS}",
        )

        # --- Proud check ---
        proud_result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="self_review_proud",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are reviewing code changes in a git diff. "
                        "Do not edit files — only provide your assessment."
                    ),
                },
                {
                    "role": "user",
                    "content": f"## Changes\n```diff\n{diff}\n```\n\n{PROUD_REVIEW_PROMPT}",
                },
            ],
            tools=[],
            max_iterations=1,
            run_id=state.get("run_id", ""),
        )
        proud_content = proud_result.get("content", "")
        total_usage.append(StageTracker.extract_token_usage(proud_result))
        proud_verdict = _extract_verdict(proud_content)
        await tracker.append_log("implement", f"  Proud check: {proud_verdict}")

        # --- World-class check ---
        wc_result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="self_review_world_class",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are reviewing code changes in a git diff. "
                        "Do not edit files — only provide your assessment."
                    ),
                },
                {
                    "role": "user",
                    "content": (f"## Changes\n```diff\n{diff}\n```\n\n{WORLD_CLASS_REVIEW_PROMPT}"),
                },
            ],
            tools=[],
            max_iterations=1,
            run_id=state.get("run_id", ""),
        )
        wc_content = wc_result.get("content", "")
        total_usage.append(StageTracker.extract_token_usage(wc_result))
        wc_verdict = _extract_verdict(wc_content)
        await tracker.append_log("implement", f"  World-class check: {wc_verdict}")

        # Both passed — exit loop
        if proud_verdict == "roadhouse!" and wc_verdict == "roadhouse!":
            await tracker.append_log("implement", "Self-review passed — roadhouse!")
            return

        # Collect feedback for the fix step
        feedback_parts: list[str] = []
        if proud_verdict == "needs-work":
            feedback_parts.append(f"## Proud Check Feedback\n{proud_content}")
        if wc_verdict == "needs-work":
            feedback_parts.append(f"## World-Class Check Feedback\n{wc_content}")
        feedback = "\n\n".join(feedback_parts)

        # Last iteration — no more fix attempts
        if iteration == MAX_SELF_REVIEW_ITERATIONS:
            await tracker.append_log(
                "implement",
                "Self-review loop exhausted — proceeding with current code",
            )
            return

        # --- Fix step ---
        await tracker.append_log("implement", "  Fixing issues from self-review...")
        fix_result = await agent_runtime.execute_step(
            thread_ref=thread_ref,
            agent_role=AgentRole.CODER,
            step_name="self_review_fix",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer. Fix the issues described "
                        "below by reading and writing files in the sandbox."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"## Current Diff\n```diff\n{diff}\n```\n\n"
                        f"## Review Feedback\n{feedback}\n\n"
                        "Fix the issues identified above."
                    ),
                },
            ],
            tools=_fix_tools(),
            max_iterations=10,
            run_id=state.get("run_id", ""),
        )
        total_usage.append(StageTracker.extract_token_usage(fix_result))
        await tracker.append_log("implement", "  Fix step complete")


def _fix_tools() -> list[dict[str, Any]]:
    """Return the tool definitions for the fix step (read + write only)."""
    from lintel.agents.sandbox_tools import SandboxToolDispatcher

    allowed = {"sandbox_read_file", "sandbox_write_file"}
    return [
        t
        for t in SandboxToolDispatcher.tool_schemas()
        if t.get("function", {}).get("name") in allowed
    ]
