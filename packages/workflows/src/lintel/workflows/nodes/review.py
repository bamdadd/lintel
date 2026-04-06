"""Review node: runs code review agent on implementation artifacts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger(__name__)

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


def _parse_findings(review_text: str) -> list[str]:
    """Extract individual findings from review text.

    Looks for numbered or bulleted items that describe issues.
    """
    findings: list[str] = []
    for line in review_text.splitlines():
        stripped = line.strip()
        # Match numbered items (1. ..., 2. ...) or bullet points (- ..., * ...)
        # Skip the verdict line itself
        if re.match(r"^(\d+[\.\)]\s+|[-*]\s+)", stripped) and "VERDICT" not in stripped.upper():
            findings.append(stripped)
    return findings


async def review_output(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Review implementation artifacts using the reviewer agent."""
    from lintel.agents.types import AgentRole
    from lintel.contracts.types import ThreadRef
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config)
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

    await tracker.mark_running("review")
    logger.info("review_started", run_id=run_id)

    sandbox_id = state.get("sandbox_id")
    diff_text = ""

    # Get the diff from the sandbox (multi-repo aware)
    if sandbox_id and sandbox_manager is not None:
        try:
            workspace_paths: tuple[tuple[str, str], ...] = state.get("workspace_paths", ())
            dirs_to_diff: list[tuple[str, str]] = []
            if workspace_paths and len(workspace_paths) > 1:
                dirs_to_diff = list(workspace_paths)
            else:
                workdir = state.get("workspace_path", "/workspace/repo")
                dirs_to_diff = [("", workdir)]

            diff_parts: list[str] = []
            for ws_url, ws_dir in dirs_to_diff:
                await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(command="git add -A", workdir=ws_dir, timeout_seconds=10),
                )
                result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(
                        command="git diff --cached",
                        workdir=ws_dir,
                        timeout_seconds=30,
                    ),
                )
                if result.stdout.strip():
                    if len(dirs_to_diff) > 1:
                        label = ws_url.rstrip("/").rsplit("/", 1)[-1] if ws_url else ws_dir
                        diff_parts.append(f"# {label}\n{result.stdout}")
                    else:
                        diff_parts.append(result.stdout)
            diff_text = "\n".join(diff_parts)
        except Exception:
            logger.warning("review_diff_collection_failed", run_id=run_id, exc_info=True)

    # Fall back to collected artifacts
    if not diff_text:
        for sr in state.get("sandbox_results", []):
            if isinstance(sr, dict) and (sr.get("content") or sr.get("diff")):
                diff_text = sr.get("content", "") or sr.get("diff", "")
                break

    if not diff_text:
        logger.info("review_skipped_no_diff", run_id=run_id)
        await tracker.mark_completed("review")
        return {
            "current_phase": "awaiting_pr_approval",
            "pending_approvals": ["pr_approval"],
            "agent_outputs": [
                {"node": "review", "verdict": "approve", "output": "No changes to review."}
            ],
            "review_decision": "approve",
            "review_findings": [],
        }

    # Truncate very large diffs for the review prompt
    if len(diff_text) > 50000:
        diff_text = diff_text[:50000] + "\n... (diff truncated)"

    await tracker.log_llm_context("review", "reviewer", "review")

    # Reconnect network — implement disconnects it, but review needs API access
    if sandbox_id and sandbox_manager is not None:
        try:
            await sandbox_manager.reconnect_network(sandbox_id)
        except Exception:
            logger.warning("review_reconnect_network_failed", run_id=run_id, exc_info=True)

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
                    await tracker.append_log("review", stripped)
            _line_buffer.clear()
            if text:
                _line_buffer.append(text)

        async def _on_activity(activity: str) -> None:
            if activity:
                await tracker.append_log("review", activity)

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
                run_id=state.get("run_id", ""),
            )
            remaining = "".join(_line_buffer).strip()
            if remaining:
                await tracker.append_log("review", remaining)
            review_output_text = agent_result.get("content", "Review complete.")
            usage = StageTracker.extract_token_usage(agent_result)
        except Exception:
            logger.exception("agent_review_failed", run_id=run_id)
            review_output_text = "Agent review failed — defaulting to manual review."
    else:
        logger.warning("review_no_agent_runtime", run_id=run_id)
        review_output_text = "No agent runtime configured — manual review required."

    # Parse verdict from review output — look for explicit VERDICT line first,
    # then fall back to keyword detection.
    verdict = "approve"
    upper_text = review_output_text.upper()

    verdict_match = re.search(r"VERDICT\s*:\s*(APPROVE|REQUEST_CHANGES)", upper_text)
    if verdict_match:
        verdict = "approve" if verdict_match.group(1) == "APPROVE" else "request_changes"
    elif "REQUEST_CHANGES" in upper_text and "APPROVE" not in upper_text:
        verdict = "request_changes"

    # Extract individual findings from the review text
    findings = _parse_findings(review_output_text)

    logger.info(
        "review_completed",
        run_id=run_id,
        verdict=verdict,
        finding_count=len(findings),
        review_length=len(review_output_text),
    )

    stage_outputs: dict[str, object] = {"verdict": verdict, "review": review_output_text}
    if usage:
        stage_outputs["token_usage"] = usage
    if findings:
        stage_outputs["findings"] = findings
    if verdict == "approve":
        await tracker.mark_completed("review", outputs=stage_outputs)
    else:
        await tracker.mark_completed("review", outputs=stage_outputs, error="Changes requested")

    # Emit audit entry for the review trail
    await _emit_review_audit(
        _configurable, run_id=run_id, verdict=verdict, finding_count=len(findings)
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
        "review_decision": verdict,
        "review_findings": findings,
    }
    if usage:
        result_dict["token_usage"] = [usage]
    return result_dict


async def _emit_review_audit(
    configurable: dict[str, Any],
    *,
    run_id: str,
    verdict: str,
    finding_count: int,
) -> None:
    """Emit an audit entry recording the review outcome."""
    app_state = configurable.get("app_state")
    if app_state is None and run_id:
        try:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            app_state = get_app_state(run_id)
        except Exception:
            return

    audit_store = getattr(app_state, "audit_entry_store", None) if app_state else None
    if audit_store is not None:
        from lintel.workflows.nodes._event_helpers import AuditEmitter

        await AuditEmitter.emit(
            audit_store,
            actor_id="reviewer-agent",
            actor_type="agent",
            action="review_completed",
            resource_type="pipeline_run",
            resource_id=run_id,
            details={"verdict": verdict, "finding_count": finding_count},
        )
