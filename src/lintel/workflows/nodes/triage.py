"""Triage workflow node — classify and prioritise incoming issues."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import AgentRole
from lintel.contracts.workflow_models import TriageResult

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


def _parse_triage(content: str) -> TriageResult:
    """Extract JSON triage result from LLM response."""
    raw: dict[str, Any] | None = None

    for fence in ("```json", "```"):
        idx = content.find(fence)
        if idx == -1:
            continue
        after = content[idx + len(fence) :]
        end_idx = after.rfind("```")
        json_str = after[:end_idx].strip() if end_idx != -1 else after.strip()
        try:
            raw = json.loads(json_str)
            break
        except json.JSONDecodeError:
            continue

    if raw is None:
        first_brace = content.find("{")
        if first_brace != -1:
            last_brace = content.rfind("}")
            if last_brace > first_brace:
                try:
                    raw = json.loads(content[first_brace : last_brace + 1])
                except json.JSONDecodeError:
                    pass

    if raw is not None and isinstance(raw, dict):
        return TriageResult(
            type=raw.get("type", "feature"),
            priority=raw.get("priority", "P2"),
            severity=raw.get("severity", "medium"),
            summary=raw.get("summary", ""),
            suggested_agents=raw.get("suggested_agents", ["planner", "coder"]),
        )

    return TriageResult(
        summary=content[:200],
    )


def _build_thread_ref(raw: str) -> ThreadRef:
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
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        extract_token_usage,
        mark_completed,
        mark_running,
    )

    await mark_running(config, "triage", state)
    await append_log(config, "triage", "Classifying issue...", state)

    agent_runtime: AgentRuntime | None = config.get("configurable", {}).get("agent_runtime")

    if agent_runtime is None:
        logger.warning("triage_no_runtime", msg="No AgentRuntime, using default classification")
        await mark_completed(config, "triage", state)
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

    content = result.content
    triage = _parse_triage(content)
    usage = extract_token_usage("triage", result)

    await append_log(config, "triage", f"Type: {triage.type}, Priority: {triage.priority}", state)
    await append_log(config, "triage", f"Summary: {triage.summary}", state)
    await append_log(
        config,
        "triage",
        f"Tokens: {usage.input_tokens} in / {usage.output_tokens} out",
        state,
    )

    logger.info(
        "triage_completed",
        issue_type=triage.type,
        priority=triage.priority,
        summary=triage.summary,
    )

    stage_outputs: dict[str, object] = {
        "token_usage": usage.model_dump(),
        "triage": triage.model_dump(),
    }
    await mark_completed(config, "triage", state, outputs=stage_outputs)

    return {
        "intent": triage.type,
        "current_phase": "triaging",
        "agent_outputs": [{"node": "triage", "agent": "pm", "content": content}],
        "token_usage": [usage.model_dump()],
    }
