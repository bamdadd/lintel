"""Cross-repo implementation plan endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.cross_repo_agent_api.store import InMemoryCrossRepoPlanStore

router = APIRouter()

cross_repo_plan_store_provider: StoreProvider[InMemoryCrossRepoPlanStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreatePlanRequest(BaseModel):
    plan_id: str | None = None
    title: str
    description: str = ""
    repositories: list[str]
    changes: list[dict[str, object]] = Field(default_factory=list)
    project_id: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/cross-repo/plans", status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    store: InMemoryCrossRepoPlanStore = Depends(cross_repo_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    from lintel.cross_repo_agent_api.store import CrossRepoPlan

    plan_id = body.plan_id if body.plan_id is not None else CrossRepoPlan().plan_id
    plan = CrossRepoPlan(
        plan_id=plan_id,
        title=body.title,
        description=body.description,
        repositories=body.repositories,
        changes=body.changes,
        project_id=body.project_id,
    )
    try:
        await store.add(plan)
    except KeyError:
        raise HTTPException(status_code=409, detail="Plan already exists")  # noqa: B904
    return asdict(plan)


@router.get("/cross-repo/plans")
async def list_plans(
    status: str | None = None,
    store: InMemoryCrossRepoPlanStore = Depends(cross_repo_plan_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    plans = await store.list_all(status=status)
    return [asdict(p) for p in plans]


@router.get("/cross-repo/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    store: InMemoryCrossRepoPlanStore = Depends(cross_repo_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return asdict(plan)


@router.post("/cross-repo/plans/{plan_id}/execute", status_code=202)
async def execute_plan(
    plan_id: str,
    store: InMemoryCrossRepoPlanStore = Depends(cross_repo_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "draft":
        raise HTTPException(status_code=409, detail="Plan is not in draft status")
    updated = await store.update(
        plan_id,
        {
            "status": "executing",
            "started_at": datetime.now(tz=UTC).isoformat(),
        },
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return asdict(updated)
