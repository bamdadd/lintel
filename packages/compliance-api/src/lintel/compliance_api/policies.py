"""Compliance policy, procedure, practice, and strategy CRUD endpoints."""

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.gdrive_service import (
    GDriveError,
    GDriveInvalidURLError,
    create_gdrive_service,
)
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    CompliancePolicyCreated,
    CompliancePolicyRemoved,
    CompliancePolicyUpdated,
    PolicyImportedFromGDrive,
    PracticeCreated,
    PracticeRemoved,
    PracticeUpdated,
    ProcedureCreated,
    ProcedureRemoved,
    ProcedureUpdated,
    StrategyCreated,
    StrategyRemoved,
    StrategyUpdated,
)
from lintel.domain.types import (
    CompliancePolicy,
    ComplianceStatus,
    Practice,
    Procedure,
    RiskLevel,
    Strategy,
)

logger = logging.getLogger(__name__)

router = APIRouter()

compliance_policy_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
procedure_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
practice_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
strategy_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


# ===================== COMPLIANCE POLICIES =====================


# ===================== GOOGLE DRIVE IMPORT =====================


class GDriveImportRequest(BaseModel):
    """Request to fetch content from a Google Drive document."""

    url: str


class GDriveImportResponse(BaseModel):
    """Response containing fetched Google Drive document content."""

    content: str
    file_id: str
    title: str


class CreateCompliancePolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    regulation_ids: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    review_date: str = ""
    tags: list[str] = []
    gdrive_source_url: str = ""


class UpdateCompliancePolicyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    regulation_ids: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    review_date: str | None = None
    tags: list[str] | None = None
    gdrive_source_url: str | None = None


@router.post("/compliance-policies/import-gdrive")
async def import_from_gdrive(body: GDriveImportRequest) -> dict[str, str]:
    """Fetch content from a Google Drive document for preview.

    This is a preview-only endpoint — it does not persist anything.
    The returned content can be used to populate the policy description field.
    """
    try:
        svc = create_gdrive_service()
        result = svc.fetch_from_url(body.url)
    except GDriveInvalidURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GDriveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/compliance-policies", status_code=201)
async def create_compliance_policy(
    request: Request,
    body: CreateCompliancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(compliance_policy_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Compliance policy already exists")
    policy = CompliancePolicy(
        policy_id=body.policy_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        regulation_ids=tuple(body.regulation_ids),
        owner=body.owner,
        status=body.status,
        risk_level=body.risk_level,
        review_date=body.review_date,
        tags=tuple(body.tags),
        gdrive_source_url=body.gdrive_source_url,
    )
    result = await store.add(policy)
    await dispatch_event(
        request,
        CompliancePolicyCreated(payload={"resource_id": body.policy_id, "name": body.name}),
        stream_id=f"compliance_policy:{body.policy_id}",
    )
    if body.gdrive_source_url:
        await dispatch_event(
            request,
            PolicyImportedFromGDrive(
                payload={
                    "policy_id": body.policy_id,
                    "gdrive_url": body.gdrive_source_url,
                }
            ),
            stream_id=f"compliance_policy:{body.policy_id}",
        )
    return result


@router.get("/compliance-policies")
async def list_compliance_policies(
    store: Annotated[ComplianceStore, Depends(compliance_policy_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/compliance-policies/{policy_id}")
async def get_compliance_policy(
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(compliance_policy_store_provider)],
) -> dict[str, Any]:
    item = await store.get(policy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    return item


@router.patch("/compliance-policies/{policy_id}")
async def update_compliance_policy(
    request: Request,
    policy_id: str,
    body: UpdateCompliancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(compliance_policy_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(policy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    await dispatch_event(
        request,
        CompliancePolicyUpdated(payload={"resource_id": policy_id}),
        stream_id=f"compliance_policy:{policy_id}",
    )
    if body.gdrive_source_url:
        await dispatch_event(
            request,
            PolicyImportedFromGDrive(
                payload={
                    "policy_id": policy_id,
                    "gdrive_url": body.gdrive_source_url,
                }
            ),
            stream_id=f"compliance_policy:{policy_id}",
        )
    return result


@router.delete("/compliance-policies/{policy_id}", status_code=204)
async def remove_compliance_policy(
    request: Request,
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(compliance_policy_store_provider)],
) -> None:
    if not await store.remove(policy_id):
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    await dispatch_event(
        request,
        CompliancePolicyRemoved(payload={"resource_id": policy_id}),
        stream_id=f"compliance_policy:{policy_id}",
    )


# ===================== PROCEDURES =====================


class CreateProcedureRequest(BaseModel):
    procedure_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    policy_ids: list[str] = []
    workflow_definition_id: str = ""
    steps: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = []


class UpdateProcedureRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    policy_ids: list[str] | None = None
    workflow_definition_id: str | None = None
    steps: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


@router.post("/procedures", status_code=201)
async def create_procedure(
    request: Request,
    body: CreateProcedureRequest,
    store: Annotated[ComplianceStore, Depends(procedure_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.procedure_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Procedure already exists")
    procedure = Procedure(
        procedure_id=body.procedure_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        policy_ids=tuple(body.policy_ids),
        workflow_definition_id=body.workflow_definition_id,
        steps=tuple(body.steps),
        owner=body.owner,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(procedure)
    await dispatch_event(
        request,
        ProcedureCreated(payload={"resource_id": body.procedure_id, "name": body.name}),
        stream_id=f"procedure:{body.procedure_id}",
    )
    return result


@router.get("/procedures")
async def list_procedures(
    store: Annotated[ComplianceStore, Depends(procedure_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/procedures/{procedure_id}")
async def get_procedure(
    procedure_id: str,
    store: Annotated[ComplianceStore, Depends(procedure_store_provider)],
) -> dict[str, Any]:
    item = await store.get(procedure_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return item


@router.patch("/procedures/{procedure_id}")
async def update_procedure(
    request: Request,
    procedure_id: str,
    body: UpdateProcedureRequest,
    store: Annotated[ComplianceStore, Depends(procedure_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(procedure_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    await dispatch_event(
        request,
        ProcedureUpdated(payload={"resource_id": procedure_id}),
        stream_id=f"procedure:{procedure_id}",
    )
    return result


@router.delete("/procedures/{procedure_id}", status_code=204)
async def remove_procedure(
    request: Request,
    procedure_id: str,
    store: Annotated[ComplianceStore, Depends(procedure_store_provider)],
) -> None:
    if not await store.remove(procedure_id):
        raise HTTPException(status_code=404, detail="Procedure not found")
    await dispatch_event(
        request,
        ProcedureRemoved(payload={"resource_id": procedure_id}),
        stream_id=f"procedure:{procedure_id}",
    )


# ===================== PRACTICES =====================


class CreatePracticeRequest(BaseModel):
    practice_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    procedure_ids: list[str] = []
    strategy_ids: list[str] = []
    evidence_type: str = ""
    automation_status: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.LOW
    tags: list[str] = []


class UpdatePracticeRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    procedure_ids: list[str] | None = None
    strategy_ids: list[str] | None = None
    evidence_type: str | None = None
    automation_status: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


@router.post("/practices", status_code=201)
async def create_practice(
    request: Request,
    body: CreatePracticeRequest,
    store: Annotated[ComplianceStore, Depends(practice_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.practice_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Practice already exists")
    practice = Practice(
        practice_id=body.practice_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        procedure_ids=tuple(body.procedure_ids),
        strategy_ids=tuple(body.strategy_ids),
        evidence_type=body.evidence_type,
        automation_status=body.automation_status,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(practice)
    await dispatch_event(
        request,
        PracticeCreated(payload={"resource_id": body.practice_id, "name": body.name}),
        stream_id=f"practice:{body.practice_id}",
    )
    return result


@router.get("/practices")
async def list_practices(
    store: Annotated[ComplianceStore, Depends(practice_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/practices/{practice_id}")
async def get_practice(
    practice_id: str,
    store: Annotated[ComplianceStore, Depends(practice_store_provider)],
) -> dict[str, Any]:
    item = await store.get(practice_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return item


@router.patch("/practices/{practice_id}")
async def update_practice(
    request: Request,
    practice_id: str,
    body: UpdatePracticeRequest,
    store: Annotated[ComplianceStore, Depends(practice_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(practice_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    await dispatch_event(
        request,
        PracticeUpdated(payload={"resource_id": practice_id}),
        stream_id=f"practice:{practice_id}",
    )
    return result


@router.delete("/practices/{practice_id}", status_code=204)
async def remove_practice(
    request: Request,
    practice_id: str,
    store: Annotated[ComplianceStore, Depends(practice_store_provider)],
) -> None:
    if not await store.remove(practice_id):
        raise HTTPException(status_code=404, detail="Practice not found")
    await dispatch_event(
        request,
        PracticeRemoved(payload={"resource_id": practice_id}),
        stream_id=f"practice:{practice_id}",
    )


# ===================== STRATEGIES =====================


class CreateStrategyRequest(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    objectives: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    tags: list[str] = []


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    objectives: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    tags: list[str] | None = None


@router.post("/strategies", status_code=201)
async def create_strategy(
    request: Request,
    body: CreateStrategyRequest,
    store: Annotated[ComplianceStore, Depends(strategy_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.strategy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Strategy already exists")
    strategy = Strategy(
        strategy_id=body.strategy_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        objectives=tuple(body.objectives),
        owner=body.owner,
        status=body.status,
        tags=tuple(body.tags),
    )
    result = await store.add(strategy)
    await dispatch_event(
        request,
        StrategyCreated(payload={"resource_id": body.strategy_id, "name": body.name}),
        stream_id=f"strategy:{body.strategy_id}",
    )
    return result


@router.get("/strategies")
async def list_strategies(
    store: Annotated[ComplianceStore, Depends(strategy_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    store: Annotated[ComplianceStore, Depends(strategy_store_provider)],
) -> dict[str, Any]:
    item = await store.get(strategy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return item


@router.patch("/strategies/{strategy_id}")
async def update_strategy(
    request: Request,
    strategy_id: str,
    body: UpdateStrategyRequest,
    store: Annotated[ComplianceStore, Depends(strategy_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(strategy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        StrategyUpdated(payload={"resource_id": strategy_id}),
        stream_id=f"strategy:{strategy_id}",
    )
    return result


@router.delete("/strategies/{strategy_id}", status_code=204)
async def remove_strategy(
    request: Request,
    strategy_id: str,
    store: Annotated[ComplianceStore, Depends(strategy_store_provider)],
) -> None:
    if not await store.remove(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        StrategyRemoved(payload={"resource_id": strategy_id}),
        stream_id=f"strategy:{strategy_id}",
    )
