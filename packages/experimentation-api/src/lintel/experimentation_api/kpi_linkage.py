"""Experiment-KPI linkage handler (REQ-034.2.4).

Subscribes to RunMetricRecorded events and auto-creates ComplianceMetric
records when metric names match configured KPI mappings.  All linkage is
event-driven through the bus to avoid tight coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.domain.types import ComplianceMetric

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

router = APIRouter()

kpi_mapping_store_provider: StoreProvider[Any] = StoreProvider()


# ---- Domain Models ----


@dataclass(frozen=True)
class KpiMapping:
    """Maps a run metric name to a KPI for automatic linkage."""

    mapping_id: str = field(default_factory=lambda: str(uuid4()))
    metric_name: str = ""
    kpi_id: str = ""
    aggregation_fn: str = "last"  # last, avg, sum, max, min
    project_id: str = ""


# ---- Event Handler ----


class KpiLinkageHandler:
    """Handles RunMetricRecorded events to create ComplianceMetric records."""

    def __init__(
        self,
        mapping_store: Any,  # noqa: ANN401
        metric_store: Any,  # noqa: ANN401
    ) -> None:
        self._mapping_store = mapping_store
        self._metric_store = metric_store

    async def handle(self, event: EventEnvelope) -> dict[str, Any] | None:
        """Process a RunMetricRecorded event.

        Returns the created ComplianceMetric dict if a mapping matched,
        or ``None`` if no mapping exists for the metric.
        """
        payload = event.payload
        metric_name = payload.get("metric_name", "")
        if not metric_name:
            return None

        mappings = await self._mapping_store.list_all()
        matching = [
            m
            for m in mappings
            if (m.get("metric_name") if isinstance(m, dict) else getattr(m, "metric_name", ""))
            == metric_name
        ]
        if not matching:
            return None

        mapping = matching[0]
        kpi_id = mapping.get("kpi_id") if isinstance(mapping, dict) else mapping.kpi_id
        project_id = mapping.get("project_id") if isinstance(mapping, dict) else mapping.project_id

        compliance_metric = ComplianceMetric(
            metric_id=str(uuid4()),
            project_id=project_id or "",
            name=metric_name,
            value=str(payload.get("value", "")),
            unit=str(payload.get("unit", "")),
            source="automated",
            kpi_ids=(str(kpi_id),) if kpi_id else (),
        )

        result = await self._metric_store.add(compliance_metric)
        return result


# ---- API Endpoints ----


class CreateKpiMappingRequest(BaseModel):
    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    metric_name: str
    kpi_id: str
    aggregation_fn: str = "last"
    project_id: str = ""


@router.post("/experiments/kpi-mappings", status_code=201)
async def create_kpi_mapping(
    body: CreateKpiMappingRequest,
    store: Any = Depends(kpi_mapping_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Register a KPI mapping."""
    existing = await store.get(body.mapping_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="KPI mapping already exists")
    mapping = KpiMapping(
        mapping_id=body.mapping_id,
        metric_name=body.metric_name,
        kpi_id=body.kpi_id,
        aggregation_fn=body.aggregation_fn,
        project_id=body.project_id,
    )
    return await store.add(mapping)


@router.get("/experiments/kpi-mappings")
async def list_kpi_mappings(
    store: Any = Depends(kpi_mapping_store_provider),  # noqa: ANN401, B008
) -> list[dict[str, Any]]:
    """List all KPI mappings."""
    return await store.list_all()


@router.delete("/experiments/kpi-mappings/{mapping_id}", status_code=204)
async def delete_kpi_mapping(
    mapping_id: str,
    store: Any = Depends(kpi_mapping_store_provider),  # noqa: ANN401, B008
) -> None:
    """Remove a KPI mapping."""
    if not await store.remove(mapping_id):
        raise HTTPException(status_code=404, detail="KPI mapping not found")
