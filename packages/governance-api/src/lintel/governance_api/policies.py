"""Governance policy CRUD endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    GovernancePolicyCreated,
    GovernancePolicyRemoved,
    GovernancePolicyUpdated,
)
from lintel.domain.types import (
    ActionScope,
    GovernanceDecision,
    GovernancePolicy,
)

router = APIRouter()

governance_policy_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateGovernancePolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    scope: ActionScope = ActionScope.TOOL_CALL
    agent_roles: list[str] = []
    default_decision: GovernanceDecision = GovernanceDecision.ALLOW
    rate_limit: int = 0
    rate_window_seconds: int = 3600
    resource_pattern: str = ""
    trust_score_threshold: float = 0.0
    enabled: bool = True
    tags: list[str] = []


class UpdateGovernancePolicyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: ActionScope | None = None
    agent_roles: list[str] | None = None
    default_decision: GovernanceDecision | None = None
    rate_limit: int | None = None
    rate_window_seconds: int | None = None
    resource_pattern: str | None = None
    trust_score_threshold: float | None = None
    enabled: bool | None = None
    tags: list[str] | None = None


@router.post("/governance/policies", status_code=201)
async def create_governance_policy(
    request: Request,
    body: CreateGovernancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(governance_policy_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Governance policy already exists")
    policy = GovernancePolicy(
        policy_id=body.policy_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        scope=body.scope,
        agent_roles=tuple(body.agent_roles),
        default_decision=body.default_decision,
        rate_limit=body.rate_limit,
        rate_window_seconds=body.rate_window_seconds,
        resource_pattern=body.resource_pattern,
        trust_score_threshold=body.trust_score_threshold,
        enabled=body.enabled,
        tags=tuple(body.tags),
    )
    result = await store.add(policy)
    await dispatch_event(
        request,
        GovernancePolicyCreated(payload={"resource_id": body.policy_id, "name": body.name}),
        stream_id=f"governance-policy:{body.policy_id}",
    )
    return result


@router.get("/governance/policies")
async def list_governance_policies(
    store: Annotated[ComplianceStore, Depends(governance_policy_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/governance/policies/{policy_id}")
async def get_governance_policy(
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(governance_policy_store_provider)],
) -> dict[str, Any]:
    item = await store.get(policy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Governance policy not found")
    return item


@router.patch("/governance/policies/{policy_id}")
async def update_governance_policy(
    request: Request,
    policy_id: str,
    body: UpdateGovernancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(governance_policy_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(policy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Governance policy not found")
    await dispatch_event(
        request,
        GovernancePolicyUpdated(payload={"resource_id": policy_id}),
        stream_id=f"governance-policy:{policy_id}",
    )
    return result


@router.delete("/governance/policies/{policy_id}", status_code=204)
async def remove_governance_policy(
    request: Request,
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(governance_policy_store_provider)],
) -> None:
    if not await store.remove(policy_id):
        raise HTTPException(status_code=404, detail="Governance policy not found")
    await dispatch_event(
        request,
        GovernancePolicyRemoved(payload={"resource_id": policy_id}),
        stream_id=f"governance-policy:{policy_id}",
    )
