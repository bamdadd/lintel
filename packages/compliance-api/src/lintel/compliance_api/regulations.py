"""Regulation CRUD endpoints and regulation template endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.seed import SEED_REGULATIONS
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import RegulationCreated, RegulationRemoved, RegulationUpdated
from lintel.domain.types import ComplianceStatus, Regulation, RiskLevel

router = APIRouter()

regulation_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateRegulationRequest(BaseModel):
    regulation_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    authority: str = ""
    reference_url: str = ""
    version: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = []


class UpdateRegulationRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    authority: str | None = None
    reference_url: str | None = None
    version: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


class AddRegulationFromTemplateRequest(BaseModel):
    template_id: str
    project_id: str


@router.post("/regulations", status_code=201)
async def create_regulation(
    request: Request,
    body: CreateRegulationRequest,
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.regulation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Regulation already exists")
    regulation = Regulation(
        regulation_id=body.regulation_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        authority=body.authority,
        reference_url=body.reference_url,
        version=body.version,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(regulation)
    await dispatch_event(
        request,
        RegulationCreated(payload={"resource_id": body.regulation_id, "name": body.name}),
        stream_id=f"regulation:{body.regulation_id}",
    )
    return result


@router.get("/regulations")
async def list_regulations(
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/regulations/{regulation_id}")
async def get_regulation(
    regulation_id: str,
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
) -> dict[str, Any]:
    item = await store.get(regulation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return item


@router.patch("/regulations/{regulation_id}")
async def update_regulation(
    request: Request,
    regulation_id: str,
    body: UpdateRegulationRequest,
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "tags" in updates:
        updates["tags"] = list(updates["tags"])
    result = await store.update(regulation_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    await dispatch_event(
        request,
        RegulationUpdated(payload={"resource_id": regulation_id}),
        stream_id=f"regulation:{regulation_id}",
    )
    return result


@router.delete("/regulations/{regulation_id}", status_code=204)
async def remove_regulation(
    request: Request,
    regulation_id: str,
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
) -> None:
    if not await store.remove(regulation_id):
        raise HTTPException(status_code=404, detail="Regulation not found")
    await dispatch_event(
        request,
        RegulationRemoved(payload={"resource_id": regulation_id}),
        stream_id=f"regulation:{regulation_id}",
    )


@router.get("/compliance/regulation-templates")
async def list_regulation_templates() -> list[dict[str, Any]]:
    """List all well-known regulation templates that can be added to projects."""
    results = []
    for reg in SEED_REGULATIONS:
        d = asdict(reg)
        for k, v in d.items():
            if isinstance(v, (tuple, frozenset)):
                d[k] = list(v)
        results.append(d)
    return results


@router.post("/compliance/regulation-from-template", status_code=201)
async def add_regulation_from_template(
    request: Request,
    body: AddRegulationFromTemplateRequest,
    store: Annotated[ComplianceStore, Depends(regulation_store_provider)],
) -> dict[str, Any]:
    """Add a regulation to a project from a well-known template."""
    template = next((r for r in SEED_REGULATIONS if r.regulation_id == body.template_id), None)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    new_id = f"{body.template_id}-{body.project_id}"
    existing = await store.get(new_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Regulation already added to this project")

    regulation = Regulation(
        regulation_id=new_id,
        project_id=body.project_id,
        name=template.name,
        description=template.description,
        authority=template.authority,
        reference_url=template.reference_url,
        version=template.version,
        status=template.status,
        risk_level=template.risk_level,
        tags=template.tags,
    )
    result = await store.add(regulation)
    await dispatch_event(
        request,
        RegulationCreated(
            payload={"resource_id": new_id, "name": template.name, "template_id": body.template_id}
        ),
        stream_id=f"regulation:{new_id}",
    )
    return result
