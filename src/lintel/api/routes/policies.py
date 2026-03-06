"""Policy CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from uuid import uuid4

from pydantic import BaseModel, Field

from lintel.contracts.types import Policy, PolicyAction

router = APIRouter()


class InMemoryPolicyStore:
    """Simple in-memory store for policies."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    async def add(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    async def get(self, policy_id: str) -> Policy | None:
        return self._policies.get(policy_id)

    async def list_all(self) -> list[Policy]:
        return list(self._policies.values())

    async def list_by_project(self, project_id: str) -> list[Policy]:
        return [p for p in self._policies.values() if p.project_id == project_id]

    async def update(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    async def remove(self, policy_id: str) -> None:
        del self._policies[policy_id]


def get_policy_store(request: Request) -> InMemoryPolicyStore:
    """Get policy store from app state."""
    return request.app.state.policy_store  # type: ignore[no-any-return]


class CreatePolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    event_type: str = ""
    condition: str = ""
    action: PolicyAction = PolicyAction.REQUIRE_APPROVAL
    approvers: list[str] = []
    project_id: str = ""


class UpdatePolicyRequest(BaseModel):
    name: str | None = None
    event_type: str | None = None
    condition: str | None = None
    action: PolicyAction | None = None
    approvers: list[str] | None = None
    project_id: str | None = None


def _policy_to_dict(policy: Policy) -> dict[str, Any]:
    data = asdict(policy)
    data["approvers"] = list(policy.approvers)
    return data


@router.post("/policies", status_code=201)
async def create_policy(
    body: CreatePolicyRequest,
    store: Annotated[InMemoryPolicyStore, Depends(get_policy_store)],
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Policy already exists")
    policy = Policy(
        policy_id=body.policy_id,
        name=body.name,
        event_type=body.event_type,
        condition=body.condition,
        action=body.action,
        approvers=tuple(body.approvers),
        project_id=body.project_id,
    )
    await store.add(policy)
    return _policy_to_dict(policy)


@router.get("/policies")
async def list_policies(
    store: Annotated[InMemoryPolicyStore, Depends(get_policy_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id is not None:
        policies = await store.list_by_project(project_id)
    else:
        policies = await store.list_all()
    return [_policy_to_dict(p) for p in policies]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    store: Annotated[InMemoryPolicyStore, Depends(get_policy_store)],
) -> dict[str, Any]:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policy_to_dict(policy)


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    body: UpdatePolicyRequest,
    store: Annotated[InMemoryPolicyStore, Depends(get_policy_store)],
) -> dict[str, Any]:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    updates = body.model_dump(exclude_none=True)
    if "approvers" in updates:
        updates["approvers"] = tuple(updates["approvers"])
    updated = Policy(**{**asdict(policy), **updates})
    await store.update(updated)
    return _policy_to_dict(updated)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str,
    store: Annotated[InMemoryPolicyStore, Depends(get_policy_store)],
) -> None:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    await store.remove(policy_id)
