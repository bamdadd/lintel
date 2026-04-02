"""Drift detection CRUD endpoints — rules, alerts, and scans."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    DriftDetected,
    DriftEscalated,
    DriftResolved,
    DriftRuleCreated,
    DriftRuleRemoved,
    DriftRuleUpdated,
    DriftScanCompleted,
    DriftScanStarted,
)
from lintel.domain.types import (
    DriftAlert,
    DriftAlertStatus,
    DriftRule,
    DriftScan,
    DriftScanStatus,
    DriftSeverity,
    DriftType,
)

if TYPE_CHECKING:
    from lintel.drift_detection_api.store import (
        InMemoryDriftAlertStore,
        InMemoryDriftRuleStore,
        InMemoryDriftScanStore,
    )

router = APIRouter()

drift_rule_store_provider: StoreProvider[InMemoryDriftRuleStore] = StoreProvider()
drift_alert_store_provider: StoreProvider[InMemoryDriftAlertStore] = StoreProvider()
drift_scan_store_provider: StoreProvider[InMemoryDriftScanStore] = StoreProvider()


# ===================== DRIFT RULES =====================


class CreateDriftRuleRequest(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    drift_type: DriftType = DriftType.CODE_INVALIDATES_ARCHITECTURE
    severity: DriftSeverity = DriftSeverity.MEDIUM
    enabled: bool = True
    source_layer: str = ""
    target_layer: str = ""
    tags: list[str] = []


class UpdateDriftRuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    drift_type: DriftType | None = None
    severity: DriftSeverity | None = None
    enabled: bool | None = None
    source_layer: str | None = None
    target_layer: str | None = None
    tags: list[str] | None = None


@router.post("/drift-rules", status_code=201)
async def create_drift_rule(
    request: Request,
    body: CreateDriftRuleRequest,
    store: InMemoryDriftRuleStore = Depends(drift_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.rule_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Drift rule already exists")
    rule = DriftRule(
        rule_id=body.rule_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        drift_type=body.drift_type,
        severity=body.severity,
        enabled=body.enabled,
        source_layer=body.source_layer,
        target_layer=body.target_layer,
        tags=tuple(body.tags),
    )
    result = await store.add(rule)
    await dispatch_event(
        request,
        DriftRuleCreated(payload={"resource_id": body.rule_id, "name": body.name}),
        stream_id=f"drift_rule:{body.rule_id}",
    )
    return result


@router.get("/drift-rules")
async def list_drift_rules(
    store: InMemoryDriftRuleStore = Depends(drift_rule_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/drift-rules/{rule_id}")
async def get_drift_rule(
    rule_id: str,
    store: InMemoryDriftRuleStore = Depends(drift_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(rule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Drift rule not found")
    return item


@router.patch("/drift-rules/{rule_id}")
async def update_drift_rule(
    request: Request,
    rule_id: str,
    body: UpdateDriftRuleRequest,
    store: InMemoryDriftRuleStore = Depends(drift_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(rule_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Drift rule not found")
    await dispatch_event(
        request,
        DriftRuleUpdated(payload={"resource_id": rule_id}),
        stream_id=f"drift_rule:{rule_id}",
    )
    return result


@router.delete("/drift-rules/{rule_id}", status_code=204)
async def delete_drift_rule(
    request: Request,
    rule_id: str,
    store: InMemoryDriftRuleStore = Depends(drift_rule_store_provider),  # noqa: B008
) -> None:
    if not await store.remove(rule_id):
        raise HTTPException(status_code=404, detail="Drift rule not found")
    await dispatch_event(
        request,
        DriftRuleRemoved(payload={"resource_id": rule_id}),
        stream_id=f"drift_rule:{rule_id}",
    )


# ===================== DRIFT ALERTS =====================


class CreateDriftAlertRequest(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    rule_id: str
    drift_type: DriftType = DriftType.CODE_INVALIDATES_ARCHITECTURE
    severity: DriftSeverity = DriftSeverity.MEDIUM
    status: DriftAlertStatus = DriftAlertStatus.OPEN
    title: str = ""
    description: str = ""
    source_ref: str = ""
    target_ref: str = ""
    remediation: str = ""
    scan_id: str = ""
    tags: list[str] = []


class UpdateDriftAlertRequest(BaseModel):
    severity: DriftSeverity | None = None
    status: DriftAlertStatus | None = None
    title: str | None = None
    description: str | None = None
    remediation: str | None = None
    tags: list[str] | None = None


@router.post("/drift-alerts", status_code=201)
async def create_drift_alert(
    request: Request,
    body: CreateDriftAlertRequest,
    store: InMemoryDriftAlertStore = Depends(drift_alert_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.alert_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Drift alert already exists")
    alert = DriftAlert(
        alert_id=body.alert_id,
        project_id=body.project_id,
        rule_id=body.rule_id,
        drift_type=body.drift_type,
        severity=body.severity,
        status=body.status,
        title=body.title,
        description=body.description,
        source_ref=body.source_ref,
        target_ref=body.target_ref,
        remediation=body.remediation,
        scan_id=body.scan_id,
        tags=tuple(body.tags),
    )
    result = await store.add(alert)
    await dispatch_event(
        request,
        DriftDetected(payload={"resource_id": body.alert_id, "rule_id": body.rule_id}),
        stream_id=f"drift_alert:{body.alert_id}",
    )
    return result


@router.get("/drift-alerts")
async def list_drift_alerts(
    store: InMemoryDriftAlertStore = Depends(drift_alert_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/drift-alerts/{alert_id}")
async def get_drift_alert(
    alert_id: str,
    store: InMemoryDriftAlertStore = Depends(drift_alert_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")
    return item


@router.patch("/drift-alerts/{alert_id}")
async def update_drift_alert(
    request: Request,
    alert_id: str,
    body: UpdateDriftAlertRequest,
    store: InMemoryDriftAlertStore = Depends(drift_alert_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(alert_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")
    event_cls = DriftResolved if updates.get("status") == "resolved" else DriftEscalated
    if "status" in updates and updates["status"] in ("resolved", "escalated"):
        await dispatch_event(
            request,
            event_cls(payload={"resource_id": alert_id}),
            stream_id=f"drift_alert:{alert_id}",
        )
    return result


@router.delete("/drift-alerts/{alert_id}", status_code=204)
async def delete_drift_alert(
    alert_id: str,
    store: InMemoryDriftAlertStore = Depends(drift_alert_store_provider),  # noqa: B008
) -> None:
    if not await store.remove(alert_id):
        raise HTTPException(status_code=404, detail="Drift alert not found")


# ===================== DRIFT SCANS =====================


class CreateDriftScanRequest(BaseModel):
    scan_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    trigger: str = ""
    tags: list[str] = []


class UpdateDriftScanRequest(BaseModel):
    status: DriftScanStatus | None = None
    alerts_found: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    tags: list[str] | None = None


@router.post("/drift-scans", status_code=201)
async def create_drift_scan(
    request: Request,
    body: CreateDriftScanRequest,
    store: InMemoryDriftScanStore = Depends(drift_scan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.scan_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Drift scan already exists")
    scan = DriftScan(
        scan_id=body.scan_id,
        project_id=body.project_id,
        trigger=body.trigger,
        tags=tuple(body.tags),
    )
    result = await store.add(scan)
    await dispatch_event(
        request,
        DriftScanStarted(payload={"resource_id": body.scan_id}),
        stream_id=f"drift_scan:{body.scan_id}",
    )
    return result


@router.get("/drift-scans")
async def list_drift_scans(
    store: InMemoryDriftScanStore = Depends(drift_scan_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/drift-scans/{scan_id}")
async def get_drift_scan(
    scan_id: str,
    store: InMemoryDriftScanStore = Depends(drift_scan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(scan_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Drift scan not found")
    return item


@router.patch("/drift-scans/{scan_id}")
async def update_drift_scan(
    request: Request,
    scan_id: str,
    body: UpdateDriftScanRequest,
    store: InMemoryDriftScanStore = Depends(drift_scan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(scan_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Drift scan not found")
    if updates.get("status") == "completed":
        await dispatch_event(
            request,
            DriftScanCompleted(payload={"resource_id": scan_id}),
            stream_id=f"drift_scan:{scan_id}",
        )
    return result


@router.delete("/drift-scans/{scan_id}", status_code=204)
async def delete_drift_scan(
    scan_id: str,
    store: InMemoryDriftScanStore = Depends(drift_scan_store_provider),  # noqa: B008
) -> None:
    if not await store.remove(scan_id):
        raise HTTPException(status_code=404, detail="Drift scan not found")
