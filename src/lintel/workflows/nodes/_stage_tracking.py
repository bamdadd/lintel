"""Helper for updating stage status in pipeline runs."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def extract_token_usage(node_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Extract token usage info from an AgentRuntime.execute_step() result."""
    usage = result.get("usage", {})
    return {
        "node": node_name,
        "model": result.get("model", ""),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }


# Map LangGraph node names to pipeline stage names.
NODE_TO_STAGE: dict[str, str] = {
    "ingest": "ingest",
    "route": "ingest",  # route is part of the ingest stage
    "setup_workspace": "ingest",  # workspace setup is part of ingest
    "plan": "plan",
    "approval_gate_spec": "approve_spec",
    "implement": "implement",
    "test": "test",
    "review": "review",
    "approval_gate_merge": "approve_merge",
    "close": "merge",
}


def _get_pipeline_store(config: dict[str, Any]) -> Any:  # noqa: ANN401
    """Extract pipeline_store from LangGraph configurable dict."""
    app_state = config.get("configurable", {}).get("app_state")
    if app_state is None:
        return None
    return getattr(app_state, "pipeline_store", None)


def _get_run_id(config: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    """Extract run_id from config or state."""
    run_id = config.get("configurable", {}).get("run_id", "")
    if not run_id and state:
        run_id = state.get("run_id", "")
    return run_id


async def mark_running(
    config: dict[str, Any],
    node_name: str,
    state: dict[str, Any] | None = None,
) -> None:
    """Mark a pipeline stage as running. Call at the start of a node."""
    stage_name = NODE_TO_STAGE.get(node_name)
    if not stage_name:
        return
    run_id = _get_run_id(config, state)
    if not run_id:
        return
    await update_stage(config, run_id, stage_name, "running")


async def append_log(
    config: dict[str, Any],
    node_name: str,
    line: str,
    state: dict[str, Any] | None = None,
) -> None:
    """Append a log line to a pipeline stage. Call during node execution."""
    stage_name = NODE_TO_STAGE.get(node_name)
    if not stage_name:
        return
    run_id = _get_run_id(config, state)
    if not run_id:
        return

    from lintel.contracts.types import Stage

    pipeline_store = _get_pipeline_store(config)
    if pipeline_store is None:
        return

    run = await pipeline_store.get(run_id)
    if run is None:
        return

    from lintel.contracts.types import PipelineRun

    new_stages: list[Stage] = []
    for s in run.stages:
        if s.name == stage_name:
            existing_logs = list(s.logs) if s.logs else []
            existing_logs.append(line)
            new_stages.append(Stage(
                stage_id=s.stage_id,
                name=s.name,
                stage_type=s.stage_type,
                status=s.status,
                inputs=s.inputs,
                outputs=s.outputs,
                error=s.error,
                duration_ms=s.duration_ms,
                started_at=s.started_at,
                finished_at=s.finished_at,
                logs=tuple(existing_logs),
                retry_count=s.retry_count,
            ))
        else:
            new_stages.append(s)

    updated = PipelineRun(
        run_id=run.run_id,
        project_id=run.project_id,
        work_item_id=run.work_item_id,
        workflow_definition_id=run.workflow_definition_id,
        status=run.status,
        stages=tuple(new_stages),
        trigger_type=run.trigger_type,
        trigger_id=run.trigger_id,
        environment_id=run.environment_id,
    )
    try:
        await pipeline_store.update(updated)
    except Exception:
        logger.warning("append_log_failed", run_id=run_id, stage_name=stage_name)


async def mark_completed(
    config: dict[str, Any],
    node_name: str,
    state: dict[str, Any] | None = None,
    outputs: dict[str, object] | None = None,
    error: str = "",
) -> None:
    """Mark a pipeline stage as succeeded or failed. Call at the end of a node."""
    stage_name = NODE_TO_STAGE.get(node_name)
    if not stage_name:
        return
    run_id = _get_run_id(config, state)
    if not run_id:
        return
    status = "failed" if error else "succeeded"
    await update_stage(config, run_id, stage_name, status, outputs=outputs, error=error)


async def update_stage(
    config: dict[str, Any],
    run_id: str,
    stage_name: str,
    status: str,
    outputs: dict[str, object] | None = None,
    error: str = "",
) -> None:
    """Update a stage's status within a pipeline run.

    Looks up the pipeline run by *run_id*, finds the stage whose ``name``
    matches *stage_name*, and replaces it with an updated copy carrying the
    new *status* (and optional *outputs* / *error*).

    This is a best-effort operation — failures are logged but not raised so
    that the workflow can continue even if tracking is unavailable.
    """
    from lintel.contracts.types import Stage, StageStatus

    pipeline_store = _get_pipeline_store(config)
    if pipeline_store is None:
        return

    run = await pipeline_store.get(run_id)
    if run is None:
        logger.warning("stage_update_run_not_found", run_id=run_id)
        return

    new_stages: list[Stage] = []
    found = False
    for s in run.stages:
        if s.name == stage_name:
            found = True
            new_stages.append(
                Stage(
                    stage_id=s.stage_id,
                    name=s.name,
                    stage_type=s.stage_type,
                    status=StageStatus(status),
                    inputs=s.inputs,
                    outputs=outputs if outputs is not None else s.outputs,
                    error=error or s.error,
                    duration_ms=s.duration_ms,
                )
            )
        else:
            new_stages.append(s)

    if not found:
        logger.warning(
            "stage_not_found_in_run",
            run_id=run_id,
            stage_name=stage_name,
        )
        return

    from lintel.contracts.types import PipelineRun

    updated = PipelineRun(
        run_id=run.run_id,
        project_id=run.project_id,
        work_item_id=run.work_item_id,
        workflow_definition_id=run.workflow_definition_id,
        status=run.status,
        stages=tuple(new_stages),
        trigger_type=run.trigger_type,
        trigger_id=run.trigger_id,
        environment_id=run.environment_id,
    )
    try:
        await pipeline_store.update(updated)
    except Exception:
        logger.warning("stage_update_failed", run_id=run_id, stage_name=stage_name)
