"""Kernel-level policy enforcement endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.kernel_policy_api.types import (
    KernelPolicy,
    KernelPolicyStatus,
    KernelPolicyType,
)

if TYPE_CHECKING:
    from lintel.kernel_policy_api.store import InMemoryKernelPolicyStore

router = APIRouter()

kernel_policy_store_provider: StoreProvider[InMemoryKernelPolicyStore] = StoreProvider()

# Track which policies are applied to which sandboxes (in-memory)
_sandbox_policies: dict[str, list[str]] = {}


class CreateKernelPolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    policy_type: KernelPolicyType
    description: str = ""
    rules: dict[str, Any] = Field(default_factory=dict)
    project_id: str = ""


class UpdateKernelPolicyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rules: dict[str, Any] | None = None
    status: KernelPolicyStatus | None = None
    project_id: str | None = None


class ApplyPolicyResponse(BaseModel):
    sandbox_id: str
    policy_id: str
    status: str


def _policy_to_dict(policy: KernelPolicy) -> dict[str, Any]:
    data = asdict(policy)
    data["policy_type"] = policy.policy_type.value
    data["status"] = policy.status.value
    return data


@router.post("/kernel-policies", status_code=201)
async def create_kernel_policy(
    body: CreateKernelPolicyRequest,
    request: Request,
    store: InMemoryKernelPolicyStore = Depends(kernel_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Kernel policy already exists")
    policy = KernelPolicy(
        policy_id=body.policy_id,
        name=body.name,
        policy_type=body.policy_type,
        description=body.description,
        rules=body.rules,
        project_id=body.project_id,
    )
    await store.add(policy)
    await dispatch_event(
        request,
        type("KernelPolicyCreated", (), {"payload": {"resource_id": policy.policy_id}})(),
        stream_id=f"kernel-policy:{policy.policy_id}",
    )
    return _policy_to_dict(policy)


@router.get("/kernel-policies")
async def list_kernel_policies(
    store: InMemoryKernelPolicyStore = Depends(kernel_policy_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    policies = await store.list_all()
    return [_policy_to_dict(p) for p in policies]


@router.get("/kernel-policies/{policy_id}")
async def get_kernel_policy(
    policy_id: str,
    store: InMemoryKernelPolicyStore = Depends(kernel_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Kernel policy not found")
    return _policy_to_dict(policy)


@router.delete("/kernel-policies/{policy_id}", status_code=204)
async def delete_kernel_policy(
    policy_id: str,
    request: Request,
    store: InMemoryKernelPolicyStore = Depends(kernel_policy_store_provider),  # noqa: B008
) -> None:
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Kernel policy not found")
    await store.remove(policy_id)
    await dispatch_event(
        request,
        type("KernelPolicyRemoved", (), {"payload": {"resource_id": policy_id}})(),
        stream_id=f"kernel-policy:{policy_id}",
    )


@router.post("/kernel-policies/apply/{sandbox_id}")
async def apply_kernel_policy(
    sandbox_id: str,
    body: dict[str, str],
    store: InMemoryKernelPolicyStore = Depends(kernel_policy_store_provider),  # noqa: B008
) -> ApplyPolicyResponse:
    policy_id = body.get("policy_id", "")
    if not policy_id:
        raise HTTPException(status_code=422, detail="policy_id is required")
    policy = await store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Kernel policy not found")
    # Record the application
    if sandbox_id not in _sandbox_policies:
        _sandbox_policies[sandbox_id] = []
    if policy_id not in _sandbox_policies[sandbox_id]:
        _sandbox_policies[sandbox_id].append(policy_id)
    # Update policy status to applied
    applied = KernelPolicy(
        policy_id=policy.policy_id,
        name=policy.name,
        policy_type=policy.policy_type,
        description=policy.description,
        rules=policy.rules,
        status=KernelPolicyStatus.APPLIED,
        project_id=policy.project_id,
    )
    await store.update(applied)
    return ApplyPolicyResponse(
        sandbox_id=sandbox_id,
        policy_id=policy_id,
        status="applied",
    )
