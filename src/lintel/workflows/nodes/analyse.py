"""Analysis workflow node — examine code/context before acting."""

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

ANALYSE_SYSTEM_PROMPT = (
    "You are a senior software analyst. Given a user request and codebase context, "
    "produce a concise analysis report in markdown with:\n\n"
    "## Summary\nOne paragraph overview of what the request involves.\n\n"
    "## Complexity Assessment\n"
    "Rate as S (trivial), M (moderate), L (significant), XL (major refactor).\n"
    "Explain why.\n\n"
    "## Risk Areas\n"
    "What could go wrong? What areas need careful attention?\n\n"
    "## Dependencies\n"
    "External libraries, services, or APIs that are relevant.\n\n"
    "## Suggested Approach\n"
    "Brief recommendation for how to proceed.\n\n"
    "Be specific — reference actual file paths and patterns from the context."
)


async def analyse_code(
    state: ThreadWorkflowState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Analyse the codebase or context to inform the next step."""
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        extract_token_usage,
        mark_completed,
        mark_running,
    )

    await mark_running(config, "analyse", state)
    await append_log(config, "analyse", "Analysing code...", state)

    _configurable = config.get("configurable", {})
    agent_runtime: AgentRuntime | None = _configurable.get("agent_runtime")
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    sandbox_id: str | None = state.get("sandbox_id")

    if agent_runtime is None:
        logger.warning("analyse_no_runtime", msg="No AgentRuntime, using stub analysis")
        await mark_completed(config, "analyse", state)
        return {
            "current_phase": "analysing",
            "agent_outputs": [{"node": "analyse", "summary": "Analysis complete (no LLM)"}],
        }

    # Gather codebase context if sandbox is available
    codebase_context = ""
    if sandbox_manager is not None and sandbox_id is not None:
        await append_log(config, "analyse", "Reading codebase from sandbox...", state)
        try:
            from lintel.workflows.nodes._codebase_context import gather_codebase_context

            workspace_path = state.get("workspace_path", "/workspace/repo")
            codebase_context = await gather_codebase_context(
                sandbox_manager, sandbox_id, repo_path=workspace_path
            )
            await append_log(
                config,
                "analyse",
                f"Codebase context: {len(codebase_context):,} chars",
                state,
            )
        except Exception:
            logger.warning("analyse_context_failed", exc_info=True)
            await append_log(config, "analyse", "Failed to read codebase context", state)

    messages_list = state.get("sanitized_messages", [])
    user_request = "\n".join(messages_list) if messages_list else "No description provided."

    # Include research context if available from upstream node
    research_context = state.get("research_context", "")
    user_content = user_request
    if codebase_context:
        user_content = f"{codebase_context}\n\n---\n\n## Request\n{user_request}"
    elif research_context:
        user_content = f"{research_context}\n\n---\n\n## Request\n{user_request}"

    from lintel.contracts.types import ThreadRef

    thread_ref_str = state.get("thread_ref", "")
    parts = thread_ref_str.split("/")
    if len(parts) == 3:
        thread_ref = ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
    else:
        thread_ref = ThreadRef(
            workspace_id="lintel-chat", channel_id="chat", thread_ts=thread_ref_str
        )

    await append_log(config, "analyse", "Running analysis with LLM...", state)

    # Stream LLM output for real-time log visibility
    _line_buffer: list[str] = []

    async def _on_chunk(chunk: str) -> None:
        _line_buffer.append(chunk)
        text = "".join(_line_buffer)
        while "\n" in text:
            line, text = text.split("\n", 1)
            stripped = line.strip()
            if stripped:
                await append_log(config, "analyse", stripped, state)
        _line_buffer.clear()
        if text:
            _line_buffer.append(text)

    result = await agent_runtime.execute_step_stream(
        thread_ref=thread_ref,
        agent_role=AgentRole.RESEARCHER,
        step_name="analyse_code",
        messages=[
            {"role": "system", "content": ANALYSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        on_chunk=_on_chunk,
    )

    remaining = "".join(_line_buffer).strip()
    if remaining:
        await append_log(config, "analyse", remaining, state)

    analysis = result.get("content", "")
    usage = extract_token_usage("analyse", result)

    await append_log(
        config,
        "analyse",
        f"Analysis complete ({len(analysis):,} chars)",
        state,
    )
    await append_log(
        config,
        "analyse",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
        state,
    )

    logger.info(
        "analyse_completed",
        analysis_chars=len(analysis),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
    )

    stage_outputs: dict[str, object] = {"token_usage": usage, "analysis": analysis}
    await mark_completed(config, "analyse", state, outputs=stage_outputs)

    return {
        "analysis_context": analysis,
        "current_phase": "analysing",
        "agent_outputs": [{"node": "analyse", "agent": "researcher", "content": analysis}],
        "token_usage": [usage],
    }
