"""Pipeline run CRUD and stage endpoints."""

import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import PipelineRun, PipelineStatus, Stage, StageStatus

router = APIRouter()

_DEFAULT_STAGE_NAMES = (
    "ingest",
    "plan",
    "approve_spec",
    "implement",
    "test",
    "review",
    "approve_merge",
    "merge",
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
        self, *, project_id: str | None = None,
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
    run_id: str
    project_id: str
    work_item_id: str
    workflow_definition_id: str = "feature_to_pr"
    trigger_type: str = ""
    trigger_id: str = ""


@router.post("/pipelines", status_code=201)
async def create_pipeline(
    body: CreatePipelineRequest,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> dict[str, Any]:
    existing = await store.get(body.run_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Pipeline run already exists")
    stages = tuple(
        Stage(
            stage_id=str(uuid.uuid4()),
            name=name,
            stage_type=name,
        )
        for name in _DEFAULT_STAGE_NAMES
    )
    run = PipelineRun(
        run_id=body.run_id,
        project_id=body.project_id,
        work_item_id=body.work_item_id,
        workflow_definition_id=body.workflow_definition_id,
        trigger_type=body.trigger_type,
        trigger_id=body.trigger_id,
        stages=stages,
    )
    await store.add(run)
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
    )
    await store.update(updated)
    return asdict(updated)


@router.delete("/pipelines/{run_id}", status_code=204)
async def delete_pipeline(
    run_id: str,
    store: Annotated[InMemoryPipelineStore, Depends(get_pipeline_store)],
) -> None:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    await store.remove(run_id)
