"""Run-level metric CRUD endpoints (REQ-034.2.1)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import RunMetricRecorded
from lintel.domain.run_metric import RunMetric

router = APIRouter()

run_metric_store_provider: StoreProvider[Any] = StoreProvider()


class CreateRunMetricRequest(BaseModel):
    metric_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    metric_name: str
    value: float
    unit: str = ""


class RunMetricResponse(BaseModel):
    metric_id: str
    run_id: str
    metric_name: str
    value: float
    unit: str
    created_at: str


@router.post("/metrics/runs", status_code=201)
async def create_run_metric(
    request: Request,
    body: CreateRunMetricRequest,
    store: Any = Depends(run_metric_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Record a run-level metric."""
    existing = await store.get(body.metric_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Run metric already exists")
    metric = RunMetric(
        metric_id=body.metric_id,
        run_id=body.run_id,
        metric_name=body.metric_name,
        value=body.value,
        unit=body.unit,
    )
    result = await store.add(metric)
    await dispatch_event(
        request,
        RunMetricRecorded(
            payload={
                "resource_id": body.metric_id,
                "run_id": body.run_id,
                "metric_name": body.metric_name,
                "value": body.value,
                "unit": body.unit,
            },
        ),
        stream_id=f"run_metric:{body.metric_id}",
    )
    return result


@router.get("/metrics/runs")
async def list_run_metrics(
    store: Any = Depends(run_metric_store_provider),  # noqa: ANN401, B008
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """List run metrics, optionally filtered by run_id."""
    if run_id:
        items = await store.list_all()
        return [i for i in items if i.get("run_id") == run_id]
    return await store.list_all()


@router.get("/metrics/runs/{metric_id}")
async def get_run_metric(
    metric_id: str,
    store: Any = Depends(run_metric_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Get a single run metric by ID."""
    item = await store.get(metric_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Run metric not found")
    return item


@router.delete("/metrics/runs/{metric_id}", status_code=204)
async def delete_run_metric(
    request: Request,
    metric_id: str,
    store: Any = Depends(run_metric_store_provider),  # noqa: ANN401, B008
) -> None:
    """Delete a run metric."""
    if not await store.remove(metric_id):
        raise HTTPException(status_code=404, detail="Run metric not found")
