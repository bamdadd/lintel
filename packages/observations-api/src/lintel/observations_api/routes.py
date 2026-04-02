"""Observation REST API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import ObservationRecorded
from lintel.domain.types import Observation

if TYPE_CHECKING:
    from lintel.observations_api.store import ObservationStore

router = APIRouter()

observation_store_provider: StoreProvider[ObservationStore] = StoreProvider()


class CreateObservationRequest(BaseModel):
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    project_id: str
    content: str
    extracted_at: str = ""
    metadata: dict[str, object] | None = None


@router.post("/observations", status_code=201)
async def create_observation(
    request: Request,
    body: CreateObservationRequest,
    store: ObservationStore = Depends(observation_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.observation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Observation already exists")
    observation = Observation(
        observation_id=body.observation_id,
        run_id=body.run_id,
        project_id=body.project_id,
        content=body.content,
        extracted_at=body.extracted_at,
        metadata=body.metadata,
    )
    result = await store.add(observation)
    await dispatch_event(
        request,
        ObservationRecorded(
            payload={"resource_id": body.observation_id, "run_id": body.run_id},
        ),
        stream_id=f"observation:{body.observation_id}",
    )
    return result


@router.get("/observations/{observation_id}")
async def get_observation(
    observation_id: str,
    store: ObservationStore = Depends(observation_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(observation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    return item


@router.get("/observations")
async def list_observations(
    store: ObservationStore = Depends(observation_store_provider),  # noqa: B008
    run_id: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if run_id:
        return await store.list_by_run(run_id)
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()
