"""Experiment CRUD endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    ComplianceExperimentCreated,
    ComplianceExperimentRemoved,
    ComplianceExperimentUpdated,
)
from lintel.domain.types import Experiment, ExperimentStatus

router = APIRouter()

experiment_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateExperimentRequest(BaseModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    hypothesis: str = ""
    description: str = ""
    strategy_ids: list[str] = []
    kpi_ids: list[str] = []
    status: ExperimentStatus = ExperimentStatus.PLANNED
    start_date: str = ""
    end_date: str = ""
    outcome: str = ""
    tags: list[str] = []


class UpdateExperimentRequest(BaseModel):
    name: str | None = None
    hypothesis: str | None = None
    description: str | None = None
    strategy_ids: list[str] | None = None
    kpi_ids: list[str] | None = None
    status: ExperimentStatus | None = None
    start_date: str | None = None
    end_date: str | None = None
    outcome: str | None = None
    tags: list[str] | None = None


@router.post("/experiments", status_code=201)
async def create_experiment(
    request: Request,
    body: CreateExperimentRequest,
    store: Annotated[ComplianceStore, Depends(experiment_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.experiment_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Experiment already exists")
    experiment = Experiment(
        experiment_id=body.experiment_id,
        project_id=body.project_id,
        name=body.name,
        hypothesis=body.hypothesis,
        description=body.description,
        strategy_ids=tuple(body.strategy_ids),
        kpi_ids=tuple(body.kpi_ids),
        status=body.status,
        start_date=body.start_date,
        end_date=body.end_date,
        outcome=body.outcome,
        tags=tuple(body.tags),
    )
    result = await store.add(experiment)
    await dispatch_event(
        request,
        ComplianceExperimentCreated(payload={"resource_id": body.experiment_id, "name": body.name}),
        stream_id=f"experiment:{body.experiment_id}",
    )
    return result


@router.get("/experiments")
async def list_experiments(
    store: Annotated[ComplianceStore, Depends(experiment_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    store: Annotated[ComplianceStore, Depends(experiment_store_provider)],
) -> dict[str, Any]:
    item = await store.get(experiment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return item


@router.patch("/experiments/{experiment_id}")
async def update_experiment(
    request: Request,
    experiment_id: str,
    body: UpdateExperimentRequest,
    store: Annotated[ComplianceStore, Depends(experiment_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(experiment_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    await dispatch_event(
        request,
        ComplianceExperimentUpdated(payload={"resource_id": experiment_id}),
        stream_id=f"experiment:{experiment_id}",
    )
    return result


@router.delete("/experiments/{experiment_id}", status_code=204)
async def remove_experiment(
    request: Request,
    experiment_id: str,
    store: Annotated[ComplianceStore, Depends(experiment_store_provider)],
) -> None:
    if not await store.remove(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    await dispatch_event(
        request,
        ComplianceExperimentRemoved(payload={"resource_id": experiment_id}),
        stream_id=f"experiment:{experiment_id}",
    )
