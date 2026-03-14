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
    "analyse the codebase context provided and "
    "produce a detailed implementation plan as JSON with the following structure:\n"
    '{"tasks": [{"title": "...", "description": "...", '
    '"file_paths": ["..."], "complexity": "S|M|L|XL"}], '
    '"summary": "one-line summary of what will be done"}\n\n'
    "Be specific about which files to change, what to add/remove, and "
    "any cascading effects (tests, APIs, types, UI).\n\n"
    "If codebase context is provided, reference actual file paths and existing "
    "patterns in your plan. Identify the right places to make changes based on "
    "the project structure and conventions you observe."
)


def _parse_plan(content: str) -> dict[str, Any]:
    """Extract JSON plan from LLM response, with fallback."""
    # Strategy 1: Find ```json ... ``` fenced block (use rfind for closing to handle nested fences)
    for fence in ("```json", "```"):
        idx = content.find(fence)
        if idx == -1:
            continue
        after = content[idx + len(fence) :]
        # Use rfind to skip past any nested code fences inside the JSON
        end_idx = after.rfind("```")
        json_str = after[:end_idx].strip() if end_idx != -1 else after.strip()
        try:
            return json.loads(json_str)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            continue

    # Strategy 2: Find outermost { ... } by matching braces
    first_brace = content.find("{")
    if first_brace != -1:
        last_brace = content.rfind("}")
        if last_brace > first_brace:
            try:
                return json.loads(content[first_brace : last_brace + 1])  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

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
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config)
    await tracker.mark_running("plan")

    # Skip if plan already populated (pipeline continuation)
    existing_plan = state.get("plan", {})
    if existing_plan and existing_plan.get("tasks"):
        await tracker.append_log("plan", "Using rehydrated plan — skipping LLM")
        await tracker.mark_completed(
            "plan",
            outputs={"plan": existing_plan, "rehydrated": True},
        )
        return {
            "plan": existing_plan,
            "current_phase": "awaiting_spec_approval",
            "pending_approvals": ["spec_approval"],
            "agent_outputs": [{"node": "plan", "summary": "Rehydrated from previous run"}],
        }

    await tracker.append_log("plan", "Generating implementation plan...")

    _configurable = config.get("configurable", {})
    agent_runtime: AgentRuntime | None = _configurable.get("agent_runtime")
    sandbox_manager = _configurable.get("sandbox_manager")
    sandbox_id: str | None = state.get("sandbox_id")

    if agent_runtime is None:
        logger.warning("plan_node_no_runtime", msg="AgentRuntime not available, using stub plan")
        await tracker.mark_completed("plan")
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

    # Use research context from the research node (upstream in the graph)
    research_context = state.get("research_context", "")
    if research_context:
        logger.info("plan_using_research_context", chars=len(research_context))
        await tracker.append_log(
            "plan",
            f"Using research context ({len(research_context):,} chars)",
        )

    # Truncate research context to avoid overwhelming the planner
    max_research_chars = 30000
    if research_context and len(research_context) > max_research_chars:
        research_context = research_context[:max_research_chars] + "\n\n...(truncated)"
        original_len = len(state.get("research_context", ""))
        logger.info("plan_research_context_truncated", original=original_len)

    # Build the user prompt with research context
    user_prompt = user_request
    if research_context:
        user_prompt = f"{research_context}\n\n---\n\n## Request\n{user_request}"

    thread_ref = _build_thread_ref(state.get("thread_ref", ""))

    await tracker.log_llm_context("plan", "planner", "plan_work")

    # Stream LLM output so partial results appear in stage logs in real-time
    _line_buffer: list[str] = []

    async def _on_chunk(chunk: str) -> None:
        """Buffer streaming chunks and flush complete lines as stage logs."""
        _line_buffer.append(chunk)
        text = "".join(_line_buffer)
        while "\n" in text:
            line, text = text.split("\n", 1)
            stripped = line.strip()
            if stripped:
                await tracker.append_log("plan", stripped)
        _line_buffer.clear()
        if text:
            _line_buffer.append(text)

    async def _on_activity(activity: str) -> None:
        """Forward Claude Code streaming activity to stage logs."""
        if activity:
            await tracker.append_log("plan", activity)

    result = await agent_runtime.execute_step_stream(
        thread_ref=thread_ref,
        agent_role=AgentRole.PLANNER,
        step_name="plan_work",
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        on_chunk=_on_chunk,
        on_activity=_on_activity,
        sandbox_manager=sandbox_manager,
        sandbox_id=sandbox_id,
        run_id=state.get("run_id", ""),
    )

    # Flush remaining buffer
    remaining = "".join(_line_buffer).strip()
    if remaining:
        await tracker.append_log("plan", remaining)

    content = result.get("content", "")
    plan = _parse_plan(content)
    plan["intent"] = state.get("intent", "feature")
    usage = StageTracker.extract_token_usage(result)

    # Log plan tasks for visibility
    summary = plan.get("summary", "")
    tasks = plan.get("tasks", [])
    await tracker.append_log("plan", f"Plan: {summary}")
    for i, task in enumerate(tasks, 1):
        title = task.get("title", task) if isinstance(task, dict) else str(task)
        complexity = task.get("complexity", "") if isinstance(task, dict) else ""
        suffix = f" [{complexity}]" if complexity else ""
        await tracker.append_log("plan", f"  {i}. {title}{suffix}")
    await tracker.append_log(
        "plan",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
    )

    logger.info(
        "plan_generated",
        task_count=len(tasks),
        summary=summary,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )

    # Store full plan in stage outputs for the detail view
    stage_outputs: dict[str, object] = {
        "token_usage": usage,
        "plan": plan,
    }
    await tracker.mark_completed("plan", outputs=stage_outputs)

    # Store plan as artifact
    _artifact_store = _configurable.get("code_artifact_store")
    if _artifact_store is None:
        _app = _configurable.get("app_state")
        if _app is not None:
            _artifact_store = getattr(_app, "code_artifact_store", None)
    if _artifact_store is not None:
        from lintel.contracts.types import CodeArtifact

        try:
            artifact = CodeArtifact(
                artifact_id=f"{state.get('run_id', '')}-plan",
                work_item_id=state.get("work_item_id", ""),
                run_id=state.get("run_id", ""),
                artifact_type="plan",
                path="",
                content=content,
            )
            await _artifact_store.add(artifact)
        except Exception:
            logger.warning("plan_artifact_storage_failed", exc_info=True)

    return {
        "plan": plan,
        "current_phase": "awaiting_spec_approval",
        "pending_approvals": ["spec_approval"],
        "agent_outputs": [{"node": "plan", "agent": "planner", "content": content}],
        "token_usage": [usage],
    }
