"""Organisation security policy CRUD and evaluation endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.org_security_api.store import InMemoryOrgSecurityPolicyStore

router = APIRouter()

org_security_policy_store_provider: StoreProvider[InMemoryOrgSecurityPolicyStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateOrgPolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str
    description: str = ""
    scope: str = "agent"
    rules: list[dict[str, object]] = Field(default_factory=list)
    action: str = "deny"
    enabled: bool = True


class EvaluateRequest(BaseModel):
    agent_id: str
    action_type: str
    resource: str
    context: dict[str, object] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/org-policies", status_code=201)
async def create_org_policy(
    body: CreateOrgPolicyRequest,
    store: InMemoryOrgSecurityPolicyStore = Depends(org_security_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Policy already exists")

    from lintel.org_security_api.store import OrgSecurityPolicy, PolicyAction, PolicyScope

    policy = OrgSecurityPolicy(
        policy_id=body.policy_id,
        name=body.name,
        description=body.description,
        scope=PolicyScope(body.scope),
        rules=body.rules,
        action=PolicyAction(body.action),
        enabled=body.enabled,
    )
    await store.add(policy)
    return asdict(policy)


@router.get("/org-policies")
async def list_org_policies(
    scope: str | None = None,
    store: InMemoryOrgSecurityPolicyStore = Depends(org_security_policy_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    policies = await store.list_all(scope=scope)
    return [asdict(p) for p in policies]


@router.get("/org-policies/{policy_id}")
async def get_org_policy(
    policy_id: str,
    store: InMemoryOrgSecurityPolicyStore = Depends(org_security_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return asdict(policy)


@router.post("/org-policies/evaluate")
async def evaluate_org_policies(
    body: EvaluateRequest,
    store: InMemoryOrgSecurityPolicyStore = Depends(org_security_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    from lintel.org_security_api.store import EvaluationResult

    policies = await store.list_all()
    violations: list[dict[str, object]] = []

    for policy in policies:
        if not policy.enabled:
            continue
        if policy.scope == body.action_type and policy.action == "deny":
            violations.append(
                {
                    "policy_id": policy.policy_id,
                    "policy_name": policy.name,
                    "scope": policy.scope,
                    "action": policy.action,
                    "resource": body.resource,
                }
            )

    result = EvaluationResult(allowed=len(violations) == 0, violations=violations)
    return asdict(result)
