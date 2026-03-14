"""Pipeline run CRUD and stage endpoints."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import asdict, replace
from datetime import UTC, datetime
import json
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lintel.contracts.events import (
    PipelineRunCancelled,
    PipelineRunDeleted,
    PipelineRunStarted,
    PipelineStageApproved,
    PipelineStageRejected,
    PipelineStageRetried,
    StageReportEdited,
    StageReportRegenerated,
)
from lintel.contracts.types import PipelineRun, PipelineStatus, Stage, StageStatus
from lintel.domain.event_dispatcher import dispatch_event

router = APIRouter()


def _stage_names_for_workflow(workflow_definition_id: str) -> tuple[str, ...]:
    """Look up stage names from the seed data for a given workflow."""
    from lintel.domain.seed import DEFAULT_WORKFLOW_DEFINITIONS

    for wf in DEFAULT_WORKFLOW_DEFINITIONS:
        if wf.definition_id == workflow_definition_id:
            return wf.stage_names
    # Fallback for custom workflows
    return (
        "ingest",
        "research",
        "approve_research",
        "plan",
        "approve_spec",
        "implement",
        "review",
        "approved_for_pr",
        "raise_pr",
    )


class InMemoryPipelineStore:
    """Simple in-memory store for pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, PipelineRun] = {}

    async def add(self, run: PipelineRun) -> None:
        self._runs[run.run_id] = run

    async def get(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    async def list_all(
        self,
        *,
        project_id: str | None = None,
    ) -> list[PipelineRun]:
        runs = list(self._runs.values())
        if project_id is not None:
            runs = [r for r in runs if r.project_id == project_id]
        return runs

    async def update(self, run: PipelineRun) -> None:
        self._runs[run.run_id] = run

    async def remove(self, run_id: str) -> None:
        del self._runs[run_id]


def get_pipeline_store(request: Request) -> InMemoryPipelineStore:
    """Get pipeline store from app state."""
    return request.app.state.pipeline_store  # type: ignore[no-any-return]


class CreatePipelineRequest(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    work_item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_definition_id: str = "feature_to_pr"
    trigger_type: str = ""
    trigger_id: str = ""


@router.post("/pipelines", status_code=201)
async def create_pipeline(
    body: CreatePipelineRequest,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    existing = await store.get(body.run_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Pipeline run already exists")
    stage_names = _stage_names_for_workflow(body.workflow_definition_id)
    stages = tuple(
        Stage(
            stage_id=str(uuid.uuid4()),
            name=name,
            stage_type=name,
        )
        for name in stage_names
    )
    from datetime import UTC, datetime

    run = PipelineRun(
        run_id=body.run_id,
        project_id=body.project_id,
        work_item_id=body.work_item_id,
        workflow_definition_id=body.workflow_definition_id,
        trigger_type=body.trigger_type,
        trigger_id=body.trigger_id,
        stages=stages,
        created_at=datetime.now(UTC).isoformat(),
    )
    await store.add(run)
    await dispatch_event(
        request,
        PipelineRunStarted(
            payload={
                "resource_id": body.run_id,
                "run_id": body.run_id,
                "project_id": body.project_id,
                "workflow": body.workflow_definition_id,
            }
        ),
        stream_id=f"run:{body.run_id}",
    )
    return asdict(run)


@router.get("/pipelines")
async def list_pipelines(
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    runs = await store.list_all(project_id=project_id)
    return [asdict(r) for r in runs]


@router.get("/pipelines/{run_id}")
async def get_pipeline(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return asdict(run)


@router.get("/pipelines/{run_id}/stages")
async def list_stages(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> list[dict[str, Any]]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return [asdict(s) for s in run.stages]


@router.get("/pipelines/{run_id}/stages/{stage_id}")
async def get_stage(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    for stage in run.stages:
        if stage.stage_id == stage_id:
            return asdict(stage)
    raise HTTPException(status_code=404, detail="Stage not found")


@router.post("/pipelines/{run_id}/cancel")
async def cancel_pipeline(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    terminal = {PipelineStatus.SUCCEEDED, PipelineStatus.FAILED, PipelineStatus.CANCELLED}
    if run.status in terminal:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel run in {run.status} state",
        )
    cancelled_stages = tuple(
        Stage(
            stage_id=s.stage_id,
            name=s.name,
            stage_type=s.stage_type,
            status=StageStatus.SKIPPED if s.status == StageStatus.PENDING else s.status,
            inputs=s.inputs,
            outputs=s.outputs,
            error=s.error,
            duration_ms=s.duration_ms,
        )
        for s in run.stages
    )
    updated = PipelineRun(
        run_id=run.run_id,
        project_id=run.project_id,
        work_item_id=run.work_item_id,
        workflow_definition_id=run.workflow_definition_id,
        status=PipelineStatus.CANCELLED,
        stages=cancelled_stages,
        trigger_type=run.trigger_type,
        trigger_id=run.trigger_id,
        created_at=run.created_at,
    )
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineRunCancelled(payload={"resource_id": run_id, "run_id": run_id}),
        stream_id=f"run:{run_id}",
    )
    return asdict(updated)


@router.delete("/pipelines/{run_id}", status_code=204)
async def delete_pipeline(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> None:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    await store.remove(run_id)
    await dispatch_event(
        request,
        PipelineRunDeleted(payload={"resource_id": run_id, "run_id": run_id}),
        stream_id=f"run:{run_id}",
    )


def _find_stage(run: PipelineRun, stage_id: str) -> Stage | None:
    for s in run.stages:
        if s.stage_id == stage_id:
            return s
    return None


class ReportVersionService:
    """Manages stage report version history stored in app state."""

    @staticmethod
    def report_key(stage_name: str) -> str:
        """Map stage name to the output key holding the report."""
        if stage_name in ("research", "approve_research"):
            return "research_report"
        if stage_name in ("plan", "approve_spec"):
            return "plan"
        return "report"

    @staticmethod
    def get_versions(
        request: Request, run_id: str, stage_id: str
    ) -> list[dict[str, object]]:
        """Retrieve report version history from app state."""
        versions_store: dict[str, list[dict[str, object]]] = getattr(
            request.app.state, "_report_versions", {}
        )
        key = f"{run_id}:{stage_id}"
        return versions_store.get(key, [])

    @staticmethod
    def add_version(
        request: Request,
        run_id: str,
        stage_id: str,
        content: str,
        editor: str,
        version_type: str = "edit",
    ) -> dict[str, object]:
        """Append a new version to the report history."""
        if not hasattr(request.app.state, "_report_versions"):
            request.app.state._report_versions = {}
        versions_store: dict[str, list[dict[str, object]]] = request.app.state._report_versions
        key = f"{run_id}:{stage_id}"
        versions = versions_store.setdefault(key, [])
        from lintel.contracts.data_models import ReportVersion

        ver = ReportVersion(
            version=len(versions) + 1,
            content=content,
            editor=editor,
            type=version_type,
            timestamp=datetime.now(UTC).isoformat(),
        )
        data = ver.model_dump()
        versions.append(data)
        return data


@router.get("/pipelines/{run_id}/stages/{stage_id}/logs")
async def stream_stage_logs(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> StreamingResponse:
    """Stream stage logs via SSE. Shows stored logs and polls for new ones."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_log_count = 0
        last_status = ""
        while True:
            run = await store.get(run_id)
            if run is None:
                return
            stage = _find_stage(run, stage_id)
            if stage is None:
                return

            # Emit any new log lines
            current_logs = list(stage.logs) if stage.logs else []
            if len(current_logs) > last_log_count:
                for line in current_logs[last_log_count:]:
                    yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
                last_log_count = len(current_logs)

            # Emit status changes
            status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
            if status != last_status:
                last_status = status
                yield f"data: {json.dumps({'type': 'status', 'status': status})}\n\n"

            # Emit outputs and error for completed/failed stages
            if status in ("succeeded", "failed", "skipped"):
                if stage.outputs:
                    payload = json.dumps(
                        {"type": "outputs", "data": stage.outputs},
                        default=str,
                    )
                    yield f"data: {payload}\n\n"
                if stage.error:
                    yield f"data: {json.dumps({'type': 'error', 'message': stage.error})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/pipelines/{run_id}/events")
async def stream_pipeline_events(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> StreamingResponse:
    """Stream pipeline stage status changes via SSE for real-time UI updates."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_statuses: dict[str, str] = {}
        last_pipeline_status = ""
        while True:
            run = await store.get(run_id)
            if run is None:
                return

            # Emit stage status changes
            for stage in run.stages:
                status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
                prev = last_statuses.get(stage.stage_id)
                if status != prev:
                    last_statuses[stage.stage_id] = status
                    payload = {
                        "type": "stage_update",
                        "stage_id": stage.stage_id,
                        "name": stage.name,
                        "status": status,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            # Emit pipeline-level status changes
            p_status = run.status.value if hasattr(run.status, "value") else str(run.status)
            if p_status != last_pipeline_status:
                last_pipeline_status = p_status
                yield f"data: {json.dumps({'type': 'pipeline_status', 'status': p_status})}\n\n"

            # End stream when pipeline reaches a terminal state
            if p_status in ("succeeded", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'pipeline_complete', 'status': p_status})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/pipelines/{run_id}/stages/{stage_id}/retry")
async def retry_stage(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    """Retry a failed or stuck stage. Resets it to running and re-invokes the node."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("running", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry stage in '{status}' state (must be running or failed)",
        )

    if stage.retry_count >= 3:
        raise HTTPException(
            status_code=409,
            detail="Maximum retry count (3) reached for this stage",
        )

    # Reset stage to running
    now = datetime.now(UTC).isoformat()
    new_stages = []
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(
                replace(
                    s,
                    status=StageStatus.RUNNING,
                    started_at=now,
                    finished_at="",
                    error="",
                    duration_ms=0,
                    logs=(),
                    retry_count=s.retry_count + 1,
                )
            )
        else:
            new_stages.append(s)

    updated = replace(run, stages=tuple(new_stages))
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageRetried(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "retry_count": stage.retry_count + 1,
            }
        ),
        stream_id=f"run:{run_id}",
    )

    # TODO: Re-invoke the workflow node via the executor (Phase 2 integration).
    # For now, the stage is reset and the executor's stream loop will pick it up
    # if the workflow is still running, or a manual re-dispatch is needed.

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


@router.post("/pipelines/{run_id}/stages/{stage_id}/reject")
async def reject_stage(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    """Reject a stage that is waiting for human approval, failing the pipeline."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status != "waiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject stage in '{status}' state (must be waiting_approval)",
        )

    # Mark stage as rejected, remaining pending stages as skipped
    new_stages = []
    rejected = False
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(replace(s, status=StageStatus.REJECTED))
            rejected = True
        elif rejected:
            s_status = s.status.value if hasattr(s.status, "value") else str(s.status)
            if s_status == "pending":
                new_stages.append(replace(s, status=StageStatus.SKIPPED))
            else:
                new_stages.append(s)
        else:
            new_stages.append(s)

    from lintel.contracts.types import PipelineStatus

    updated = replace(
        run,
        stages=tuple(new_stages),
        status=PipelineStatus.FAILED,
    )
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageRejected(
            payload={"resource_id": stage_id, "run_id": run_id, "stage_name": stage.name}
        ),
        stream_id=f"run:{run_id}",
    )

    # Clean up suspended run in executor
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        executor._suspended_runs.pop(run_id, None)

    # Fail the work item
    if executor is not None and hasattr(executor, "_app_state") and executor._app_state:
        work_item_store = getattr(executor._app_state, "work_item_store", None)
        pipeline_store = getattr(executor._app_state, "pipeline_store", None)
        if work_item_store and pipeline_store:
            try:
                full_run = await pipeline_store.get(run_id)
                if full_run and hasattr(full_run, "trigger_type"):
                    trigger = full_run.trigger_type
                    if trigger.startswith("chat:"):
                        conversation_id = trigger[5:]
                        chat_store = getattr(executor._app_state, "chat_store", None)
                        if chat_store:
                            await chat_store.add_message(
                                conversation_id,
                                user_id="system",
                                display_name="Lintel",
                                role="agent",
                                content=(
                                    f"🚫 **{stage.name}** — rejected\n"
                                    f"Pipeline has been stopped.\n"
                                    f"[View pipeline →](/pipelines/{run_id})"
                                ),
                            )
            except Exception:
                pass

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


@router.post("/pipelines/{run_id}/stages/{stage_id}/approve")
async def approve_stage(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    """Approve a stage that is waiting for human approval and resume the workflow."""
    import asyncio

    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status != "waiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve stage in '{status}' state (must be waiting_approval)",
        )

    # Mark stage as approved
    new_stages = []
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(replace(s, status=StageStatus.APPROVED))
        else:
            new_stages.append(s)

    from lintel.contracts.types import PipelineStatus

    updated = replace(
        run,
        stages=tuple(new_stages),
        status=PipelineStatus.RUNNING,
    )
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageApproved(
            payload={"resource_id": stage_id, "run_id": run_id, "stage_name": stage.name}
        ),
        stream_id=f"run:{run_id}",
    )

    # Resume the workflow in the background
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        task = asyncio.create_task(executor.resume(run_id))
        request.app.state._background_tasks = getattr(
            request.app.state,
            "_background_tasks",
            set(),
        )
        request.app.state._background_tasks.add(task)
        task.add_done_callback(request.app.state._background_tasks.discard)

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


# --- Stage Report Editing (REQ-013) ---


class ReportEditPayload(BaseModel):
    """Body for editing a stage report."""

    content: str = Field(..., description="Updated report content (Markdown)")
    editor: str = Field(default="user", description="Who made the edit")


class RegeneratePayload(BaseModel):
    """Body for regenerating a stage report."""

    guidance: str = Field(default="", description="Optional prompt to guide regeneration")




@router.patch("/pipelines/{run_id}/stages/{stage_id}/report")
async def edit_stage_report(
    run_id: str,
    stage_id: str,
    body: ReportEditPayload,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    """Edit the report output of a completed or waiting_approval stage."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("succeeded", "waiting_approval"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit report in '{status}' state",
        )

    # Update the report in stage outputs
    rkey = ReportVersionService.report_key(stage.name)
    outputs = dict(stage.outputs) if stage.outputs else {}
    outputs[rkey] = body.content

    new_stages = [replace(s, outputs=outputs) if s.stage_id == stage_id else s for s in run.stages]
    updated = replace(run, stages=tuple(new_stages))
    await store.update(updated)

    # Record version
    version = ReportVersionService.add_version(request, run_id, stage_id, body.content, body.editor)

    await dispatch_event(
        request,
        StageReportEdited(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "editor": body.editor,
                "version": version["version"],
            }
        ),
        stream_id=f"run:{run_id}",
    )

    return {
        "stage_id": stage_id,
        "report_key": rkey,
        "version": version["version"],
        "content": body.content,
    }


@router.get("/pipelines/{run_id}/stages/{stage_id}/report/versions")
async def list_report_versions(
    run_id: str,
    stage_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> list[dict[str, object]]:
    """List all versions of a stage report."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    return ReportVersionService.get_versions(request, run_id, stage_id)


@router.post("/pipelines/{run_id}/stages/{stage_id}/regenerate")
async def regenerate_stage(
    run_id: str,
    stage_id: str,
    body: RegeneratePayload,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
    request: Request,
) -> dict[str, Any]:
    """Re-run a stage with optional guidance, resetting it to running."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("succeeded", "waiting_approval", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regenerate stage in '{status}' state",
        )

    # Store guidance in stage inputs for the node to pick up
    now = datetime.now(UTC).isoformat()
    inputs = dict(stage.inputs) if stage.inputs else {}
    if body.guidance:
        inputs["regenerate_guidance"] = body.guidance

    new_stages = [
        replace(
            s,
            status=StageStatus.RUNNING,
            started_at=now,
            finished_at="",
            error="",
            duration_ms=0,
            outputs=None,
            logs=(),
            inputs=inputs or None,
            retry_count=s.retry_count + 1,
        )
        if s.stage_id == stage_id
        else s
        for s in run.stages
    ]

    updated = replace(run, stages=tuple(new_stages), status=PipelineStatus.RUNNING)
    await store.update(updated)

    ReportVersionService.add_version(
        request,
        run_id,
        stage_id,
        f"[Regenerating: {body.guidance or 'no guidance'}]",
        "system",
        version_type="regenerate",
    )

    await dispatch_event(
        request,
        StageReportRegenerated(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "guidance": body.guidance,
            }
        ),
        stream_id=f"run:{run_id}",
    )

    # Resume workflow execution for regeneration
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        task = asyncio.create_task(executor.resume(run_id))
        request.app.state._background_tasks = getattr(request.app.state, "_background_tasks", set())
        request.app.state._background_tasks.add(task)
        task.add_done_callback(request.app.state._background_tasks.discard)

    regen_stage = _find_stage(updated, stage_id)
    return asdict(regen_stage)  # type: ignore[arg-type]
