"""Synthesis REST API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import SynthesisGenerated
from lintel.domain.types import Synthesis

if TYPE_CHECKING:
    from lintel.syntheses_api.store import SynthesisStore

router = APIRouter()

synthesis_store_provider: StoreProvider[SynthesisStore] = StoreProvider()


class CreateSynthesisRequest(BaseModel):
    synthesis_id: str = Field(default_factory=lambda: str(uuid4()))
    hypothesis: str
    source_observation_ids: list[str] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    created_at: str = ""


@router.post("/syntheses", status_code=201)
async def create_synthesis(
    request: Request,
    body: CreateSynthesisRequest,
    store: SynthesisStore = Depends(synthesis_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.synthesis_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Synthesis already exists")
    synthesis = Synthesis(
        synthesis_id=body.synthesis_id,
        hypothesis=body.hypothesis,
        source_observation_ids=tuple(body.source_observation_ids),
        project_ids=tuple(body.project_ids),
        confidence_score=body.confidence_score,
        created_at=body.created_at,
    )
    result = await store.add(synthesis)
    await dispatch_event(
        request,
        SynthesisGenerated(
            payload={
                "resource_id": body.synthesis_id,
                "confidence_score": body.confidence_score,
            },
        ),
        stream_id=f"synthesis:{body.synthesis_id}",
    )
    return result


@router.get("/syntheses/{synthesis_id}")
async def get_synthesis(
    synthesis_id: str,
    store: SynthesisStore = Depends(synthesis_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(synthesis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return item


@router.get("/syntheses")
async def list_syntheses(
    store: SynthesisStore = Depends(synthesis_store_provider),  # noqa: B008
    project_id: str | None = None,
    min_confidence: float | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    if min_confidence is not None:
        return await store.list_by_min_confidence(min_confidence)
    return await store.list_all()
