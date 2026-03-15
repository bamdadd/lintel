"""Architecture decision record (ADR) CRUD endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    ArchitectureDecisionCreated,
    ArchitectureDecisionRemoved,
    ArchitectureDecisionUpdated,
)
from lintel.domain.types import ADRStatus, ArchitectureDecision

router = APIRouter()

architecture_decision_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateArchitectureDecisionRequest(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: str = ""
    superseded_by: str = ""
    regulation_ids: list[str] = []
    tags: list[str] = []
    date_proposed: str = ""
    date_decided: str = ""
    deciders: list[str] = []


class UpdateArchitectureDecisionRequest(BaseModel):
    title: str | None = None
    status: ADRStatus | None = None
    context: str | None = None
    decision: str | None = None
    consequences: str | None = None
    alternatives: str | None = None
    superseded_by: str | None = None
    regulation_ids: list[str] | None = None
    tags: list[str] | None = None
    date_proposed: str | None = None
    date_decided: str | None = None
    deciders: list[str] | None = None


@router.post("/architecture-decisions", status_code=201)
async def create_architecture_decision(
    body: CreateArchitectureDecisionRequest,
    request: Request,
    store: Annotated[ComplianceStore, Depends(architecture_decision_store_provider)],
) -> dict[str, Any]:
    adr = ArchitectureDecision(
        decision_id=body.decision_id,
        project_id=body.project_id,
        title=body.title,
        status=body.status,
        context=body.context,
        decision=body.decision,
        consequences=body.consequences,
        alternatives=body.alternatives,
        superseded_by=body.superseded_by,
        regulation_ids=tuple(body.regulation_ids),
        tags=tuple(body.tags),
        date_proposed=body.date_proposed,
        date_decided=body.date_decided,
        deciders=tuple(body.deciders),
    )
    existing = await store.get(body.decision_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Decision already exists")
    result = await store.add(adr)
    await dispatch_event(
        request,
        ArchitectureDecisionCreated(
            payload={"resource_id": body.decision_id, "title": body.title},
        ),
        stream_id=f"architecture-decision:{body.decision_id}",
    )
    return result


@router.get("/architecture-decisions")
async def list_architecture_decisions(
    store: Annotated[ComplianceStore, Depends(architecture_decision_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/architecture-decisions/{decision_id}")
async def get_architecture_decision(
    decision_id: str,
    store: Annotated[ComplianceStore, Depends(architecture_decision_store_provider)],
) -> dict[str, Any]:
    result = await store.get(decision_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return result


@router.patch("/architecture-decisions/{decision_id}")
async def update_architecture_decision(
    decision_id: str,
    body: UpdateArchitectureDecisionRequest,
    request: Request,
    store: Annotated[ComplianceStore, Depends(architecture_decision_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "regulation_ids" in updates:
        updates["regulation_ids"] = tuple(updates["regulation_ids"])
    if "tags" in updates:
        updates["tags"] = tuple(updates["tags"])
    if "deciders" in updates:
        updates["deciders"] = tuple(updates["deciders"])
    result = await store.update(decision_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    await dispatch_event(
        request,
        ArchitectureDecisionUpdated(
            payload={"resource_id": decision_id},
        ),
        stream_id=f"architecture-decision:{decision_id}",
    )
    return result


@router.delete("/architecture-decisions/{decision_id}", status_code=204)
async def delete_architecture_decision(
    decision_id: str,
    request: Request,
    store: Annotated[ComplianceStore, Depends(architecture_decision_store_provider)],
) -> None:
    removed = await store.remove(decision_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Decision not found")
    await dispatch_event(
        request,
        ArchitectureDecisionRemoved(
            payload={"resource_id": decision_id},
        ),
        stream_id=f"architecture-decision:{decision_id}",
    )
