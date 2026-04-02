"""Agent trust score CRUD endpoints (REQ-F029)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    TrustScoreAdjusted,
    TrustScoreCreated,
    TrustScoreRemoved,
)
from lintel.trust_scores_api.store import InMemoryTrustScoreStore  # noqa: TC001
from lintel.trust_scores_api.types import (
    AutonomyTier,
    TrustFactor,
    TrustFactorKind,
    TrustHistory,
    TrustScore,
    _autonomy_tier_for_score,
)

router = APIRouter()

trust_score_store_provider: StoreProvider[InMemoryTrustScoreStore] = StoreProvider()


class CreateTrustScoreRequest(BaseModel):
    agent_id: str
    score: int = Field(default=500, ge=0, le=1000)
    sponsor: str = ""


class AdjustTrustScoreRequest(BaseModel):
    kind: TrustFactorKind = TrustFactorKind.MANUAL_ADJUSTMENT
    delta: int = Field(ge=-1000, le=1000)
    reason: str = ""
    created_by: str = ""


class UpdateTrustScoreRequest(BaseModel):
    sponsor: str | None = None
    score: int | None = Field(default=None, ge=0, le=1000)


@router.post("/trust-scores", status_code=201)
async def create_trust_score(
    request: Request,
    body: CreateTrustScoreRequest,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.agent_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Trust score already exists for this agent")
    tier = _autonomy_tier_for_score(body.score)
    trust_score = TrustScore(
        agent_id=body.agent_id,
        score=body.score,
        tier=tier,
        sponsor=body.sponsor,
    )
    result = await store.add(trust_score)
    await dispatch_event(
        request,
        TrustScoreCreated(
            payload={"resource_id": body.agent_id, "score": body.score, "tier": tier.value},
        ),
        stream_id=f"trust-score:{body.agent_id}",
    )
    return result


@router.get("/trust-scores")
async def list_trust_scores(
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/trust-scores/{agent_id}")
async def get_trust_score(
    agent_id: str,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> dict[str, Any]:
    item = await store.get(agent_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trust score not found")
    return item


@router.patch("/trust-scores/{agent_id}")
async def update_trust_score(
    request: Request,
    agent_id: str,
    body: UpdateTrustScoreRequest,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(agent_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Trust score not found")
    return result


@router.post("/trust-scores/{agent_id}/adjust", status_code=200)
async def adjust_trust_score(
    request: Request,
    agent_id: str,
    body: AdjustTrustScoreRequest,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> dict[str, Any]:
    """Apply a trust score adjustment and record the factor in history."""
    current = await store.get(agent_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Trust score not found")

    old_score = current["score"]
    new_score = max(0, min(1000, old_score + body.delta))
    old_tier = AutonomyTier(current["tier"])
    new_tier = _autonomy_tier_for_score(new_score)

    await store.update(agent_id, {"score": new_score, "tier": new_tier})

    factor = TrustFactor(
        agent_id=agent_id,
        kind=body.kind,
        delta=body.delta,
        reason=body.reason,
        created_by=body.created_by,
    )
    history = TrustHistory(
        history_id=str(uuid4()),
        agent_id=agent_id,
        score_before=old_score,
        score_after=new_score,
        tier_before=old_tier,
        tier_after=new_tier,
        factor=factor,
    )
    await store.add_history(history)

    await dispatch_event(
        request,
        TrustScoreAdjusted(
            payload={
                "resource_id": agent_id,
                "delta": body.delta,
                "score_before": old_score,
                "score_after": new_score,
                "tier": new_tier.value,
                "kind": body.kind.value,
            },
        ),
        stream_id=f"trust-score:{agent_id}",
    )

    updated = await store.get(agent_id)
    assert updated is not None
    return updated


@router.get("/trust-scores/{agent_id}/history")
async def get_trust_history(
    agent_id: str,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> list[dict[str, Any]]:
    current = await store.get(agent_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Trust score not found")
    return await store.get_history(agent_id)


@router.delete("/trust-scores/{agent_id}", status_code=204)
async def delete_trust_score(
    request: Request,
    agent_id: str,
    store: Annotated[InMemoryTrustScoreStore, Depends(trust_score_store_provider)],
) -> None:
    if not await store.remove(agent_id):
        raise HTTPException(status_code=404, detail="Trust score not found")
    await dispatch_event(
        request,
        TrustScoreRemoved(payload={"resource_id": agent_id}),
        stream_id=f"trust-score:{agent_id}",
    )
