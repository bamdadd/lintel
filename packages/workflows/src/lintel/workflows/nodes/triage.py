"""Triage workflow node — classify and prioritise incoming issues."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import AgentRole

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

TRIAGE_SYSTEM_PROMPT = (
    "You are an expert issue triager for software projects. "
    "Given a user request, classify it and return JSON with:\n"
    '{"type": "bug|feature|refactor|docs|test|chore", '
    '"priority": "P0|P1|P2|P3", '
    '"severity": "critical|high|medium|low", '
    '"summary": "one-line summary", '
    '"suggested_agents": ["planner", "coder", "researcher"]}\n\n'
    "P0 = production down, P1 = major impact, P2 = moderate, P3 = minor.\n"
    "severity reflects technical risk. suggested_agents lists which roles should handle this."
)


def _parse_triage(content: str) -> dict[str, Any]:
    """Extract JSON triage result from LLM response."""
    for fence in ("```json", "```"):
        idx = content.find(fence)
        if idx == -1:
            continue
        after = content[idx + len(fence) :]
        end_idx = after.rfind("```")
        json_str = after[:end_idx].strip() if end_idx != -1 else after.strip()
        try:
            return json.loads(json_str)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            continue

    first_brace = content.find("{")
    if first_brace != -1:
        last_brace = content.rfind("}")
        if last_brace > first_brace:
            try:
                return json.loads(content[first_brace : last_brace + 1])  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

    return {
        "type": "feature",
        "priority": "P2",
        "severity": "medium",
        "summary": content[:200],
        "suggested_agents": ["planner", "coder"],
    }


def _build_thread_ref(raw: str) -> Any:  # noqa: ANN401
    """Reconstruct ThreadRef from its string representation."""
    from lintel.contracts.types import ThreadRef

    parts = raw.split("/")
    if len(parts) == 3:
        return ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
    return ThreadRef(workspace_id="lintel-chat", channel_id="chat", thread_ts=raw)


async def triage_issue(
    state: ThreadWorkflowState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Classify issue type, severity, and route to the right agent."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("triage")
    await tracker.append_log("triage", "Classifying issue...")

    agent_runtime: AgentRuntime | None = config.get("configurable", {}).get("agent_runtime")

    if agent_runtime is None:
        logger.warning("triage_no_runtime", msg="No AgentRuntime, using default classification")
        await tracker.mark_completed("triage")
        return {
            "intent": "feature",
            "current_phase": "triaging",
            "agent_outputs": [{"node": "triage", "classification": "feature", "priority": "P2"}],
        }

    messages_list = state.get("sanitized_messages", [])
    user_request = "\n".join(messages_list) if messages_list else "No description provided."
    thread_ref = _build_thread_ref(state.get("thread_ref", ""))

    result = await agent_runtime.execute_step(
        thread_ref=thread_ref,
        agent_role=AgentRole.PM,
        step_name="triage_issue",
        messages=[
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
        tools=[],
    )

    content = result.get("content", "")
    triage = _parse_triage(content)
    usage = StageTracker.extract_token_usage(result)

    issue_type = triage.get("type", "feature")
    priority = triage.get("priority", "P2")
    summary = triage.get("summary", "")

    await tracker.append_log("triage", f"Type: {issue_type}, Priority: {priority}")
    await tracker.append_log("triage", f"Summary: {summary}")
    await tracker.append_log(
        "triage",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
    )

    logger.info(
        "triage_completed",
        issue_type=issue_type,
        priority=priority,
        summary=summary,
    )

    stage_outputs: dict[str, object] = {"token_usage": usage, "triage": triage}
    await tracker.mark_completed("triage", outputs=stage_outputs)

    return {
        "intent": issue_type,
        "current_phase": "triaging",
        "agent_outputs": [{"node": "triage", "agent": "pm", "content": content}],
        "token_usage": [usage],
    }
