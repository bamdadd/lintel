"""Compliance metric CRUD endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    ComplianceMetricCreated,
    ComplianceMetricRemoved,
    ComplianceMetricUpdated,
)
from lintel.domain.types import ComplianceMetric

router = APIRouter()

compliance_metric_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateComplianceMetricRequest(BaseModel):
    metric_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    value: str = ""
    unit: str = ""
    source: str = ""
    kpi_ids: list[str] = []
    collected_at: str = ""
    tags: list[str] = []


class UpdateComplianceMetricRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    value: str | None = None
    unit: str | None = None
    source: str | None = None
    kpi_ids: list[str] | None = None
    collected_at: str | None = None
    tags: list[str] | None = None


@router.post("/compliance-metrics", status_code=201)
async def create_compliance_metric(
    request: Request,
    body: CreateComplianceMetricRequest,
    store: Annotated[ComplianceStore, Depends(compliance_metric_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.metric_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Compliance metric already exists")
    metric = ComplianceMetric(
        metric_id=body.metric_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        value=body.value,
        unit=body.unit,
        source=body.source,
        kpi_ids=tuple(body.kpi_ids),
        collected_at=body.collected_at,
        tags=tuple(body.tags),
    )
    result = await store.add(metric)
    await dispatch_event(
        request,
        ComplianceMetricCreated(payload={"resource_id": body.metric_id, "name": body.name}),
        stream_id=f"compliance_metric:{body.metric_id}",
    )
    return result


@router.get("/compliance-metrics")
async def list_compliance_metrics(
    store: Annotated[ComplianceStore, Depends(compliance_metric_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/compliance-metrics/{metric_id}")
async def get_compliance_metric(
    metric_id: str,
    store: Annotated[ComplianceStore, Depends(compliance_metric_store_provider)],
) -> dict[str, Any]:
    item = await store.get(metric_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance metric not found")
    return item


@router.patch("/compliance-metrics/{metric_id}")
async def update_compliance_metric(
    request: Request,
    metric_id: str,
    body: UpdateComplianceMetricRequest,
    store: Annotated[ComplianceStore, Depends(compliance_metric_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(metric_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Compliance metric not found")
    await dispatch_event(
        request,
        ComplianceMetricUpdated(payload={"resource_id": metric_id}),
        stream_id=f"compliance_metric:{metric_id}",
    )
    return result


@router.delete("/compliance-metrics/{metric_id}", status_code=204)
async def remove_compliance_metric(
    request: Request,
    metric_id: str,
    store: Annotated[ComplianceStore, Depends(compliance_metric_store_provider)],
) -> None:
    if not await store.remove(metric_id):
        raise HTTPException(status_code=404, detail="Compliance metric not found")
    await dispatch_event(
        request,
        ComplianceMetricRemoved(payload={"resource_id": metric_id}),
        stream_id=f"compliance_metric:{metric_id}",
    )
