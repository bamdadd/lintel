"""Hook configuration API routes.

Thin wrappers around the trigger store, filtered to triggers where
hook_type IS NOT NULL. These endpoints provide a hook-specific view
of the trigger system for REQ-012.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.domain.events import TriggerCreated, TriggerRemoved, TriggerUpdated
from lintel.domain.types import HookType, Trigger, TriggerType
from lintel.triggers_api.routes import trigger_store_provider

if TYPE_CHECKING:
    from lintel.triggers_api.store import InMemoryTriggerStore

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateHookRequest(BaseModel):
    """Request body for creating a hook."""

    hook_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    hook_type: HookType
    event_pattern: str
    trigger_type: TriggerType = TriggerType.WEBHOOK
    config: dict[str, object] | None = None
    condition: str | None = None
    max_chain_depth: int = 5
    enabled: bool = True


class UpdateHookRequest(BaseModel):
    """Request body for updating a hook."""

    name: str | None = None
    hook_type: HookType | None = None
    event_pattern: str | None = None
    config: dict[str, object] | None = None
    condition: str | None = None
    max_chain_depth: int | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/hooks")
async def list_hooks(
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all hook-type triggers."""
    triggers = await store.list_all(project_id=project_id)
    hooks = [t for t in triggers if t.hook_type is not None]
    return [asdict(h) for h in hooks]


@router.post("/hooks", status_code=201)
async def create_hook(
    body: CreateHookRequest,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a trigger with hook_type set."""
    existing = await store.get(body.hook_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Hook already exists")
    trigger = Trigger(
        trigger_id=body.hook_id,
        project_id=body.project_id,
        trigger_type=body.trigger_type,
        name=body.name,
        config=body.config,
        enabled=body.enabled,
        hook_type=body.hook_type,
        event_pattern=body.event_pattern,
        condition=body.condition,
        max_chain_depth=body.max_chain_depth,
    )
    await store.add(trigger)
    await dispatch_event(
        request,
        TriggerCreated(
            payload={"resource_id": trigger.trigger_id, "hook_type": body.hook_type.value}
        ),
        stream_id=f"trigger:{trigger.trigger_id}",
    )
    return asdict(trigger)


@router.get("/hooks/{hook_id}")
async def get_hook(
    hook_id: str,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific hook by ID."""
    trigger = await store.get(hook_id)
    if trigger is None or trigger.hook_type is None:
        raise HTTPException(status_code=404, detail="Hook not found")
    return asdict(trigger)


@router.put("/hooks/{hook_id}")
async def update_hook(
    hook_id: str,
    body: UpdateHookRequest,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update a hook."""
    trigger = await store.get(hook_id)
    if trigger is None or trigger.hook_type is None:
        raise HTTPException(status_code=404, detail="Hook not found")
    updates = body.model_dump(exclude_none=True)
    updated = Trigger(**{**asdict(trigger), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        TriggerUpdated(payload={"resource_id": hook_id}),
        stream_id=f"trigger:{hook_id}",
    )
    return asdict(updated)


@router.delete("/hooks/{hook_id}", status_code=204)
async def delete_hook(
    hook_id: str,
    request: Request,
    store: InMemoryTriggerStore = Depends(trigger_store_provider),  # noqa: B008
) -> None:
    """Delete a hook."""
    trigger = await store.get(hook_id)
    if trigger is None or trigger.hook_type is None:
        raise HTTPException(status_code=404, detail="Hook not found")
    await store.remove(hook_id)
    await dispatch_event(
        request,
        TriggerRemoved(payload={"resource_id": hook_id}),
        stream_id=f"trigger:{hook_id}",
    )
