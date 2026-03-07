"""Helper for updating stage status in pipeline runs.

TODO: Wire this into workflow nodes once pipeline_store is accessible
via LangGraph config (requires injecting app_state into the configurable dict).
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def update_stage(
    app_state: Any,  # noqa: ANN401
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

    pipeline_store = getattr(app_state, "pipeline_store", None)
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
