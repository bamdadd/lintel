"""Ingest node: processes incoming message through PII firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState


async def ingest_message(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Process message. PII firewall runs before this node."""
    from lintel.workflows.nodes._stage_tracking import append_log, mark_completed, mark_running

    _config = config or {}
    await mark_running(_config, "ingest", state)

    # Log trigger source
    _configurable = _config.get("configurable", {}) if isinstance(_config, dict) else {}
    run_id = state.get("run_id", "")
    trigger_type = ""
    work_item_id = state.get("work_item_id", "")

    # Resolve trigger type from pipeline run
    pipeline_store = _configurable.get("pipeline_store")
    if pipeline_store is None:
        app_state = _configurable.get("app_state")
        if app_state is not None:
            pipeline_store = getattr(app_state, "pipeline_store", None)

    if pipeline_store is not None and run_id:
        try:
            run = await pipeline_store.get(run_id)
            if run is not None:
                trigger_type = (
                    run.trigger_type
                    if hasattr(run, "trigger_type")
                    else run.get("trigger_type", "")
                )
        except Exception:
            pass

    # Determine and log trigger source
    if trigger_type.startswith("work_item:"):
        await append_log(_config, "ingest", f"Triggered by work item: `{work_item_id}`", state)
    elif trigger_type.startswith("chat:"):
        conv_id = trigger_type.split(":", 1)[1] if ":" in trigger_type else ""
        await append_log(_config, "ingest", f"Triggered from chat: `{conv_id}`", state)
    elif trigger_type:
        await append_log(_config, "ingest", f"Trigger: {trigger_type}", state)

    # Log the prompt/request
    messages = state.get("sanitized_messages", [])
    if messages:
        prompt = messages[0] if isinstance(messages[0], str) else str(messages[0])
        # Truncate long prompts for readability
        display = prompt[:500] + "..." if len(prompt) > 500 else prompt
        await append_log(_config, "ingest", f"Request: {display}", state)

    await mark_completed(_config, "ingest", state)

    return {
        "current_phase": "ingesting",
        "sanitized_messages": messages,
    }
