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
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config)
    await tracker.mark_running("ingest")

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
        await tracker.append_log("ingest", f"Triggered by work item: `{work_item_id}`")
    elif trigger_type.startswith("chat:"):
        conv_id = trigger_type.split(":", 1)[1] if ":" in trigger_type else ""
        await tracker.append_log("ingest", f"Triggered from chat: `{conv_id}`")
    elif trigger_type:
        await tracker.append_log("ingest", f"Trigger: {trigger_type}")

    # Always log the prompt/request so the UI shows what was asked
    messages = state.get("sanitized_messages", [])
    prompt = ""
    if messages:
        prompt = messages[0] if isinstance(messages[0], str) else str(messages[0])
    elif work_item_id and pipeline_store is not None:
        # Fall back to work item description
        work_item_store = _configurable.get("work_item_store")
        if work_item_store is None:
            app_state = _configurable.get("app_state")
            if app_state is not None:
                work_item_store = getattr(app_state, "work_item_store", None)
        if work_item_store is not None:
            try:
                wi = await work_item_store.get(work_item_id)
                if wi is not None:
                    prompt = (
                        wi.description if hasattr(wi, "description") else wi.get("description", "")
                    )
            except Exception:
                pass

    if prompt:
        display = prompt[:500] + "..." if len(prompt) > 500 else prompt
        await tracker.append_log("ingest", f"Request: {display}")

    await tracker.mark_completed("ingest")

    return {
        "current_phase": "ingesting",
        "sanitized_messages": messages,
    }
