"""Pipeline-level route handlers: create, list, get, cancel, delete."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.pipelines_api._helpers import _stage_names_for_workflow
from lintel.pipelines_api._store import InMemoryPipelineStore, pipeline_store_provider
from lintel.workflows.events import (
    PipelineRunCancelled,
    PipelineRunDeleted,
    PipelineRunStarted,
)
from lintel.workflows.types import PipelineRun, PipelineStatus, Stage, StageStatus

router = APIRouter()


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
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
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
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    runs = await store.list_all(project_id=project_id)
    return [asdict(r) for r in runs]


@router.get("/pipelines/{run_id}")
async def get_pipeline(
    run_id: str,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return asdict(run)


@router.post("/pipelines/{run_id}/cancel")
async def cancel_pipeline(
    run_id: str,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
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
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
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
