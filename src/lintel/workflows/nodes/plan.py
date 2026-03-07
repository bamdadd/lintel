"""Plan node: generates implementation plan via agent runtime."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import AgentRole

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.types import ThreadRef
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

PLAN_SYSTEM_PROMPT = (
    "You are a senior software planner. Given a feature request or bug report, "
    "produce a detailed implementation plan as JSON with the following structure:\n"
    '{"tasks": [{"title": "...", "description": "...", "complexity": "S|M|L|XL"}], '
    '"summary": "one-line summary of what will be done"}\n\n'
    "Be specific about which files to change, what to add/remove, and "
    "any cascading effects (tests, APIs, types, UI)."
)


def _parse_plan(content: str) -> dict[str, Any]:
    """Extract JSON plan from LLM response, with fallback."""
    # Try to find JSON block in response
    for start, end in [("```json", "```"), ("```", "```"), ("{", None)]:
        idx = content.find(start)
        if idx == -1:
            continue
        json_str = content[idx + len(start) :]
        if end and end != start:
            end_idx = json_str.find(end)
            if end_idx != -1:
                json_str = json_str[:end_idx]
        elif start == "{":
            json_str = start + json_str
        try:
            return json.loads(json_str.strip())  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            continue
    # Fallback: return raw content as single task
    return {
        "tasks": [{"title": "Implement request", "description": content}],
        "summary": content[:200],
    }


def _build_thread_ref(raw: str) -> ThreadRef:
    """Reconstruct ThreadRef from its string representation."""
    from lintel.contracts.types import ThreadRef

    parts = raw.split("/")
    if len(parts) == 3:
        return ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
    return ThreadRef(workspace_id="lintel-chat", channel_id="chat", thread_ts=raw)


async def plan_work(state: ThreadWorkflowState, config: RunnableConfig) -> dict[str, Any]:
    """Generate work plan using the Planner agent via AgentRuntime."""
    agent_runtime: AgentRuntime | None = config.get("configurable", {}).get("agent_runtime")

    if agent_runtime is None:
        logger.warning("plan_node_no_runtime", msg="AgentRuntime not available, using stub plan")
        return {
            "plan": {
                "tasks": [{"title": t} for t in ["Implement feature", "Write tests", "Create PR"]],
                "intent": state.get("intent", "feature"),
            },
            "current_phase": "awaiting_spec_approval",
            "pending_approvals": ["spec_approval"],
        }

    messages = state.get("sanitized_messages", [])
    user_request = "\n".join(messages) if messages else "No description provided."

    thread_ref = _build_thread_ref(state.get("thread_ref", ""))

    result = await agent_runtime.execute_step(
        thread_ref=thread_ref,
        agent_role=AgentRole.PLANNER,
        step_name="plan_work",
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
    )

    content = result.get("content", "")
    plan = _parse_plan(content)
    plan["intent"] = state.get("intent", "feature")

    logger.info(
        "plan_generated",
        task_count=len(plan.get("tasks", [])),
        summary=plan.get("summary", ""),
    )

    return {
        "plan": plan,
        "current_phase": "awaiting_spec_approval",
        "pending_approvals": ["spec_approval"],
        "agent_outputs": [{"node": "plan", "agent": "planner", "content": content}],
    }
