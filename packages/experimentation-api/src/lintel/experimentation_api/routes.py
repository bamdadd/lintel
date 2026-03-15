"""Experimentation endpoints: KPIs, experiments, and compliance metrics."""

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
    ComplianceMetricCreated,
    ComplianceMetricRemoved,
    ComplianceMetricUpdated,
    KPICreated,
    KPIRemoved,
    KPIUpdated,
)
from lintel.domain.types import (
    KPI,
    ComplianceMetric,
    ComplianceStatus,
    Experiment,
    ExperimentStatus,
    KPIDirection,
)

router = APIRouter()

# Store providers
kpi_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
experiment_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
compliance_metric_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


# ===================== KPIs =====================


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


# ===================== EXPERIMENTS =====================


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


# ===================== COMPLIANCE METRICS =====================


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
