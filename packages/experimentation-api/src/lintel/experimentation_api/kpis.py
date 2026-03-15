"""KPI CRUD endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import KPICreated, KPIRemoved, KPIUpdated
from lintel.domain.types import (
    KPI,
    ComplianceStatus,
    KPIDirection,
)

router = APIRouter()

kpi_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateKPIRequest(BaseModel):
    kpi_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    target_value: str = ""
    current_value: str = ""
    unit: str = ""
    direction: KPIDirection = KPIDirection.INCREASE
    strategy_ids: list[str] = []
    threshold_warning: str = ""
    threshold_critical: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    tags: list[str] = []


class UpdateKPIRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    target_value: str | None = None
    current_value: str | None = None
    unit: str | None = None
    direction: KPIDirection | None = None
    strategy_ids: list[str] | None = None
    threshold_warning: str | None = None
    threshold_critical: str | None = None
    status: ComplianceStatus | None = None
    tags: list[str] | None = None


@router.post("/kpis", status_code=201)
async def create_kpi(
    request: Request,
    body: CreateKPIRequest,
    store: Annotated[ComplianceStore, Depends(kpi_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.kpi_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="KPI already exists")
    kpi = KPI(
        kpi_id=body.kpi_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        target_value=body.target_value,
        current_value=body.current_value,
        unit=body.unit,
        direction=body.direction,
        strategy_ids=tuple(body.strategy_ids),
        threshold_warning=body.threshold_warning,
        threshold_critical=body.threshold_critical,
        status=body.status,
        tags=tuple(body.tags),
    )
    result = await store.add(kpi)
    await dispatch_event(
        request,
        KPICreated(payload={"resource_id": body.kpi_id, "name": body.name}),
        stream_id=f"kpi:{body.kpi_id}",
    )
    return result


@router.get("/kpis")
async def list_kpis(
    store: Annotated[ComplianceStore, Depends(kpi_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/kpis/{kpi_id}")
async def get_kpi(
    kpi_id: str,
    store: Annotated[ComplianceStore, Depends(kpi_store_provider)],
) -> dict[str, Any]:
    item = await store.get(kpi_id)
    if item is None:
        raise HTTPException(status_code=404, detail="KPI not found")
    return item


@router.patch("/kpis/{kpi_id}")
async def update_kpi(
    request: Request,
    kpi_id: str,
    body: UpdateKPIRequest,
    store: Annotated[ComplianceStore, Depends(kpi_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(kpi_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="KPI not found")
    await dispatch_event(
        request,
        KPIUpdated(payload={"resource_id": kpi_id}),
        stream_id=f"kpi:{kpi_id}",
    )
    return result


@router.delete("/kpis/{kpi_id}", status_code=204)
async def remove_kpi(
    request: Request,
    kpi_id: str,
    store: Annotated[ComplianceStore, Depends(kpi_store_provider)],
) -> None:
    if not await store.remove(kpi_id):
        raise HTTPException(status_code=404, detail="KPI not found")
    await dispatch_event(
        request,
        KPIRemoved(payload={"resource_id": kpi_id}),
        stream_id=f"kpi:{kpi_id}",
    )
