"""Proactive trigger management REST endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.proactive_triggers_api.store import (
        InMemoryProactiveTriggerStore,
        InMemoryTriggerExecutionStore,
    )

router = APIRouter()

proactive_trigger_store_provider: StoreProvider[InMemoryProactiveTriggerStore] = StoreProvider()
trigger_execution_store_provider: StoreProvider[InMemoryTriggerExecutionStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateProactiveTriggerRequest(BaseModel):
    """Request body for creating a proactive trigger."""

    trigger_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    event_pattern: str
    agent_definition_id: str
    project_id: str
    config: dict[str, object] | None = None
    enabled: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/proactive-triggers", status_code=201)
async def create_proactive_trigger(
    body: CreateProactiveTriggerRequest,
    store: InMemoryProactiveTriggerStore = Depends(proactive_trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Define an event pattern that auto-launches an agent."""
    from lintel.proactive_triggers_api.store import ProactiveTrigger

    existing = await store.get(body.trigger_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Proactive trigger already exists")
    trigger = ProactiveTrigger(
        trigger_id=body.trigger_id,
        name=body.name,
        event_pattern=body.event_pattern,
        agent_definition_id=body.agent_definition_id,
        project_id=body.project_id,
        config=body.config,
        enabled=body.enabled,
    )
    await store.add(trigger)
    return asdict(trigger)


@router.get("/proactive-triggers")
async def list_proactive_triggers(
    project_id: str | None = None,
    store: InMemoryProactiveTriggerStore = Depends(proactive_trigger_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all proactive triggers, optionally filtered by project."""
    triggers = await store.list_all(project_id=project_id)
    return [asdict(t) for t in triggers]


@router.get("/proactive-triggers/history")
async def list_trigger_executions(
    trigger_id: str | None = None,
    store: InMemoryTriggerExecutionStore = Depends(trigger_execution_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List past proactive trigger executions."""
    executions = await store.list_all(trigger_id=trigger_id)
    return [asdict(e) for e in executions]


@router.get("/proactive-triggers/{trigger_id}")
async def get_proactive_trigger(
    trigger_id: str,
    store: InMemoryProactiveTriggerStore = Depends(proactive_trigger_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a single proactive trigger by ID."""
    trigger = await store.get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Proactive trigger not found")
    return asdict(trigger)


@router.delete("/proactive-triggers/{trigger_id}", status_code=204)
async def delete_proactive_trigger(
    trigger_id: str,
    store: InMemoryProactiveTriggerStore = Depends(proactive_trigger_store_provider),  # noqa: B008
) -> None:
    """Remove a proactive trigger."""
    trigger = await store.get(trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Proactive trigger not found")
    await store.remove(trigger_id)
