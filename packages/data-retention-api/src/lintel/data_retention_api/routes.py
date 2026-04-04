"""Data retention policy CRUD and execution endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.data_retention_api.store import InMemoryRetentionPolicyStore, RetentionPolicy
from lintel.domain.events import (
    RetentionPolicyCreated,
    RetentionPolicyRemoved,
    RetentionRunCompleted,
)

router = APIRouter()

retention_policy_store_provider: StoreProvider = StoreProvider()


class CreateRetentionPolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str
    max_age_days: int = Field(gt=0)
    action: str = Field(pattern=r"^(delete|archive)$")
    description: str = ""


class RunRetentionRequest(BaseModel):
    dry_run: bool = False


@router.post("/retention/policies", status_code=201)
async def create_retention_policy(
    body: CreateRetentionPolicyRequest,
    request: Request,
    store: InMemoryRetentionPolicyStore = Depends(retention_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Retention policy already exists")
    policy = RetentionPolicy(
        policy_id=body.policy_id,
        entity_type=body.entity_type,
        max_age_days=body.max_age_days,
        action=body.action,
        description=body.description,
    )
    await store.add(policy)
    await dispatch_event(
        request,
        RetentionPolicyCreated(payload={"resource_id": policy.policy_id}),
        stream_id=f"retention_policy:{policy.policy_id}",
    )
    return asdict(policy)


@router.get("/retention/policies")
async def list_retention_policies(
    store: InMemoryRetentionPolicyStore = Depends(retention_policy_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    policies = await store.list_all()
    return [asdict(p) for p in policies]


@router.get("/retention/policies/{policy_id}")
async def get_retention_policy(
    policy_id: str,
    store: InMemoryRetentionPolicyStore = Depends(retention_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    return asdict(policy)


@router.delete("/retention/policies/{policy_id}", status_code=204)
async def delete_retention_policy(
    policy_id: str,
    request: Request,
    store: InMemoryRetentionPolicyStore = Depends(retention_policy_store_provider),  # noqa: B008
) -> None:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    await store.remove(policy_id)
    await dispatch_event(
        request,
        RetentionPolicyRemoved(payload={"resource_id": policy_id}),
        stream_id=f"retention_policy:{policy_id}",
    )


@router.post("/retention/run")
async def run_retention(
    body: RunRetentionRequest,
    request: Request,
    store: InMemoryRetentionPolicyStore = Depends(retention_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    policies = await store.list_all()
    affected: list[dict[str, Any]] = []
    for policy in policies:
        affected.append(
            {
                "policy_id": policy.policy_id,
                "entity_type": policy.entity_type,
                "action": policy.action,
                "max_age_days": policy.max_age_days,
                "items_matched": 0,
            }
        )
    result = {
        "run_id": str(uuid4()),
        "dry_run": body.dry_run,
        "started_at": datetime.now(tz=UTC).isoformat(),
        "policies_evaluated": len(policies),
        "results": affected,
    }
    await dispatch_event(
        request,
        RetentionRunCompleted(payload={"run_id": result["run_id"]}),
        stream_id=f"retention_run:{result['run_id']}",
    )
    return result
