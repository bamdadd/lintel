"""Trigger CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import TriggerCreated, TriggerRemoved, TriggerUpdated
from lintel.domain.types import Trigger, TriggerType
from lintel.triggers_api.store import InMemoryTriggerStore

router = APIRouter()

trigger_store_provider = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTriggerRequest(BaseModel):
    trigger_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    trigger_type: TriggerType
    name: str
    config: dict[str, object] | None = None
    enabled: bool = True


class UpdateTriggerRequest(BaseModel):
    name: str | None = None
    config: dict[str, object] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/triggers", status_code=201)
async def create_trigger(
    body: CreateTriggerRequest,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.trigger_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Trigger already exists")
    trigger = Trigger(
        trigger_id=body.trigger_id,
        project_id=body.project_id,
        trigger_type=body.trigger_type,
        name=body.name,
        config=body.config,
        enabled=body.enabled,
    )
    await store.add(trigger)
    await dispatch_event(
        request,
        TriggerCreated(payload={"resource_id": trigger.trigger_id}),
        stream_id=f"trigger:{trigger.trigger_id}",
    )
    return asdict(trigger)


@router.get("/triggers")
async def list_triggers(
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    triggers = await store.list_all(project_id=project_id)
    return [asdict(t) for t in triggers]


@router.get("/triggers/{trigger_id}")
async def get_trigger(
    trigger_id: str,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    trigger = await store.get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return asdict(trigger)


@router.patch("/triggers/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    body: UpdateTriggerRequest,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    trigger = await store.get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    updates = body.model_dump(exclude_none=True)
    updated = Trigger(**{**asdict(trigger), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        TriggerUpdated(payload={"resource_id": trigger_id}),
        stream_id=f"trigger:{trigger_id}",
    )
    return asdict(updated)


@router.delete("/triggers/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: str,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> None:
    trigger = await store.get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await store.remove(trigger_id)
    await dispatch_event(
        request,
        TriggerRemoved(payload={"resource_id": trigger_id}),
        stream_id=f"trigger:{trigger_id}",
    )
