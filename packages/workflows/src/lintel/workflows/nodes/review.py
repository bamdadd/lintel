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
You are a pragmatic senior code reviewer. Review the following git diff for:
1. Correctness — does the code do what it should?
2. Security — any obvious vulnerabilities (injection, secrets, etc.)?
3. Quality — reasonable code structure and naming?

IMPORTANT: Be pragmatic. Only REQUEST_CHANGES for genuine bugs, security issues, \
or broken functionality. Do NOT request changes for:
- Style preferences or minor naming choices
- Missing tests for simple UI pages
- Unbounded retries or minor edge cases that don't affect correctness
- Suggestions that are "nice to have" but not required

Provide a concise review with:
- VERDICT: APPROVE or REQUEST_CHANGES
- Summary of findings
- Specific issues (if any)

Default to APPROVE unless there is a real problem.
"""


async def review_output(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Review implementation artifacts using the reviewer agent."""
    from lintel.contracts.types import AgentRole, SandboxJob, ThreadRef
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

    # Fall back to runtime registry after LangGraph interrupt/resume
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

    await mark_running(_config, "review", state)

    sandbox_id = state.get("sandbox_id")
    diff_text = ""

    # Get the diff from the sandbox
    if sandbox_id and sandbox_manager is not None:
        try:
            workdir = state.get("workspace_path", "/workspace/repo")
            # Stage new files so they appear in the diff
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="git add -A", workdir=workdir, timeout_seconds=10),
            )
            result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command="git diff --cached",
                    workdir=workdir,
                    timeout_seconds=30,
                ),
            )
            diff_text = result.stdout
        except Exception:
            logger.warning("review_diff_collection_failed")

    # Fall back to collected artifacts
    if not diff_text:
        for sr in state.get("sandbox_results", []):
            if isinstance(sr, dict) and (sr.get("content") or sr.get("diff")):
                diff_text = sr.get("content", "") or sr.get("diff", "")
                break

    if not diff_text:
        await mark_completed(_config, "review", state)
        return {
            "current_phase": "awaiting_pr_approval",
            "pending_approvals": ["pr_approval"],
            "agent_outputs": [
                {"node": "review", "verdict": "approve", "output": "No changes to review."}
            ],
        }

    # Truncate very large diffs for the review prompt
    if len(diff_text) > 50000:
        diff_text = diff_text[:50000] + "\n... (diff truncated)"

    from lintel.workflows.nodes._stage_tracking import log_llm_context

    await log_llm_context(_config, "review", "reviewer", "review", state)

    # Reconnect network — implement disconnects it, but review needs API access
    if sandbox_id and sandbox_manager is not None:
        try:
            await sandbox_manager.reconnect_network(sandbox_id)
        except Exception:
            logger.warning("review_reconnect_network_failed")

    review_output_text = ""
    usage: dict[str, Any] | None = None
    if agent_runtime is not None:
        thread_ref_str = state["thread_ref"]
        parts = thread_ref_str.replace("thread:", "").split(":")
        thread_ref = ThreadRef(
            workspace_id=parts[0] if len(parts) > 0 else "",
            channel_id=parts[1] if len(parts) > 1 else "",
            thread_ts=parts[2] if len(parts) > 2 else "",
        )

        _line_buffer: list[str] = []

        async def _on_chunk(chunk: str) -> None:
            _line_buffer.append(chunk)
            text = "".join(_line_buffer)
            while "\n" in text:
                line, text = text.split("\n", 1)
                stripped = line.strip()
                if stripped:
                    await append_log(_config, "review", stripped, state)
            _line_buffer.clear()
            if text:
                _line_buffer.append(text)

        async def _on_activity(activity: str) -> None:
            if activity:
                await append_log(_config, "review", activity, state)

        try:
            agent_result = await agent_runtime.execute_step_stream(
                thread_ref=thread_ref,
                agent_role=AgentRole.REVIEWER,
                step_name="review",
                messages=[
                    {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": f"```diff\n{diff_text}\n```"},
                ],
                on_chunk=_on_chunk,
                on_activity=_on_activity,
                sandbox_manager=sandbox_manager,
                sandbox_id=sandbox_id,
            )
            remaining = "".join(_line_buffer).strip()
            if remaining:
                await append_log(_config, "review", remaining, state)
            review_output_text = agent_result.get("content", "Review complete.")
            usage = extract_token_usage("review", agent_result)
        except Exception:
            logger.exception("agent_review_failed")
            review_output_text = "Agent review failed — defaulting to manual review."
    else:
        review_output_text = "No agent runtime configured — manual review required."

    # Parse verdict from review output — look for explicit VERDICT line first,
    # then fall back to keyword detection.
    verdict = "approve"
    upper_text = review_output_text.upper()

    import re

    verdict_match = re.search(r"VERDICT\s*:\s*(APPROVE|REQUEST_CHANGES)", upper_text)
    if verdict_match:
        verdict = "approve" if verdict_match.group(1) == "APPROVE" else "request_changes"
    elif "REQUEST_CHANGES" in upper_text and "APPROVE" not in upper_text:
        verdict = "request_changes"

    logger.info("review_verdict_parsed verdict=%s", verdict)

    stage_outputs: dict[str, object] = {"verdict": verdict, "review": review_output_text}
    if usage:
        stage_outputs["token_usage"] = usage
    if verdict == "approve":
        await mark_completed(_config, "review", state, outputs=stage_outputs)
    else:
        await mark_completed(
            _config, "review", state, outputs=stage_outputs, error="Changes requested"
        )

    # Disconnect network again after review
    if sandbox_id and sandbox_manager is not None:
        import contextlib

        with contextlib.suppress(Exception):
            await sandbox_manager.disconnect_network(sandbox_id)

    review_cycles = state.get("review_cycles", 0) + 1

    result_dict: dict[str, Any] = {
        "current_phase": "awaiting_pr_approval" if verdict == "approve" else "implementing",
        "pending_approvals": ["pr_approval"] if verdict == "approve" else [],
        "agent_outputs": [{"node": "review", "verdict": verdict, "output": review_output_text}],
        "review_cycles": review_cycles,
    }
    if usage:
        result_dict["token_usage"] = [usage]
    return result_dict
