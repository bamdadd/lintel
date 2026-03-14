"""Research node: surveys the codebase in the sandbox to build context for planning."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.contracts.types import AgentRole

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime
    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

RESEARCH_SYSTEM_PROMPT = (
    "You are a senior software researcher. Your job is to examine a codebase and "
    "produce a concise research report that will help a planner write an implementation plan.\n\n"
    "You will be given:\n"
    "1. A user request describing what needs to change\n"
    "2. Codebase context: directory structure, key files, class/function definitions\n\n"
    "Produce a research report in markdown with these sections:\n"
    "## Relevant Files\n"
    "List the files most relevant to the request with a one-line description of each.\n\n"
    "## Current Architecture\n"
    "Briefly describe how the relevant parts of the codebase work today.\n\n"
    "## Key Patterns\n"
    "Note any conventions, patterns, or dependencies the planner should follow.\n\n"
    "## Impact Analysis\n"
    "What other parts of the codebase would be affected by the change? "
    "List tests, APIs, types, and UI components that may need updates.\n\n"
    "## Recommendations\n"
    "Brief suggestions for how to approach the implementation.\n\n"
    "Be specific — reference actual file paths and code patterns from the context provided. "
    "Keep the report under 1500 words."
)


async def _gather_context(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    repo_path: str = "/workspace/repo",
) -> str:
    """Gather codebase context from the sandbox."""
    from lintel.workflows.nodes._codebase_context import gather_codebase_context

    return await gather_codebase_context(sandbox_manager, sandbox_id, repo_path=repo_path)


async def research_codebase(
    state: ThreadWorkflowState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Research the codebase to produce context for the planning stage."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config)
    await tracker.mark_running("research")
    await tracker.append_log("research", "Researching codebase...")

    _configurable = config.get("configurable", {})
    agent_runtime: AgentRuntime | None = _configurable.get("agent_runtime")
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    sandbox_id: str | None = state.get("sandbox_id")

    # Gather codebase context from sandbox (if available)
    codebase_context = ""
    if sandbox_manager is not None and sandbox_id is not None:
        await tracker.append_log("research", "Reading codebase from sandbox...")
        try:
            workspace_path = state.get("workspace_path") or "/workspace/repo"
            codebase_context = await _gather_context(sandbox_manager, sandbox_id, workspace_path)
        except Exception:
            logger.warning("research_sandbox_context_failed", exc_info=True)
            await tracker.append_log("research", "Failed to read codebase from sandbox")
            # Continue without codebase context — LLM can still analyse the request

    if codebase_context:
        await tracker.append_log(
            "research",
            f"Codebase context gathered ({len(codebase_context):,} chars)",
        )
    else:
        await tracker.append_log(
            "research",
            "No codebase context available — analysing request only",
        )

    # Without agent runtime, return raw context as research
    if agent_runtime is None:
        logger.warning("research_no_runtime", msg="No AgentRuntime, using raw codebase context")
        await tracker.mark_completed(
            "research",
            outputs={
                "research_report": codebase_context,
            },
        )
        return {
            "research_context": codebase_context,
            "current_phase": "planning",
            "agent_outputs": [{"node": "research", "summary": "Raw codebase context (no LLM)"}],
        }

    # Build the user request from sanitized messages
    messages = state.get("sanitized_messages", [])
    user_request = "\n".join(messages) if messages else "No description provided."

    # Ask the LLM to produce a structured research report
    label = (
        "Analysing codebase with LLM..." if codebase_context else "Analysing request with LLM..."
    )
    await tracker.append_log("research", label)

    from lintel.contracts.types import ThreadRef

    thread_ref_str = state.get("thread_ref", "")
    parts = thread_ref_str.split("/")
    if len(parts) == 3:
        thread_ref = ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
    else:
        thread_ref = ThreadRef(
            workspace_id="lintel-chat", channel_id="chat", thread_ts=thread_ref_str
        )

    # Stream LLM output so partial results appear in stage logs in real-time
    await tracker.log_llm_context("research", "researcher", "research_codebase")

    _line_buffer: list[str] = []

    async def _on_chunk(chunk: str) -> None:
        """Buffer streaming chunks and flush complete lines as stage logs."""
        _line_buffer.append(chunk)
        text = "".join(_line_buffer)
        # Flush complete lines
        while "\n" in text:
            line, text = text.split("\n", 1)
            stripped = line.strip()
            if stripped:
                await tracker.append_log("research", stripped)
        _line_buffer.clear()
        if text:
            _line_buffer.append(text)

    async def _on_activity(activity: str) -> None:
        """Forward Claude Code streaming activity to stage logs."""
        if activity:
            await tracker.append_log("research", activity)

    result = await agent_runtime.execute_step_stream(
        thread_ref=thread_ref,
        agent_role=AgentRole.RESEARCHER,
        step_name="research_codebase",
        messages=[
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{codebase_context}\n\n---\n\n## User Request\n{user_request}"
                    if codebase_context
                    else f"## User Request\n{user_request}\n\n"
                    "Note: No codebase context available. Analyse the request and provide "
                    "recommendations based on general software engineering best practices."
                ),
            },
        ],
        on_chunk=_on_chunk,
        on_activity=_on_activity,
        sandbox_manager=sandbox_manager,
        sandbox_id=sandbox_id,
    )

    # Flush any remaining buffered content
    remaining = "".join(_line_buffer).strip()
    if remaining:
        await tracker.append_log("research", remaining)

    research_report = result.get("content", "")
    usage = StageTracker.extract_token_usage(result)

    await tracker.append_log("research", f"Research complete ({len(research_report):,} chars)")
    await tracker.append_log(
        "research",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
    )

    logger.info(
        "research_completed",
        report_chars=len(research_report),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )

    stage_outputs: dict[str, object] = {
        "token_usage": usage,
        "research_report": research_report,
    }
    await tracker.mark_completed("research", outputs=stage_outputs)

    return {
        "research_context": research_report,
        "current_phase": "planning",
        "agent_outputs": [{"node": "research", "agent": "researcher", "content": research_report}],
        "token_usage": [usage],
    }
