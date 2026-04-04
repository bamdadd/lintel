"""Workflow ACL CRUD and check endpoints."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.domain.types import AclRule
from lintel.workflow_acl_api.store import InMemoryAclRuleStore  # noqa: TC001

router = APIRouter()

acl_rule_store_provider: StoreProvider[InMemoryAclRuleStore] = StoreProvider()


# --- Request / Response models ---


class CreateAclRuleRequest(BaseModel):
    connection_id: str
    workflow_types: list[str] = Field(default_factory=list)
    project_id: str = ""
    effect: str = "deny"


class AclCheckRequest(BaseModel):
    connection_id: str
    workflow_type: str
    project_id: str = ""


class AclCheckResult(BaseModel):
    allowed: bool
    reason: str


# --- Endpoints ---


@router.post("/workflow-acl/rules", status_code=201)
async def create_acl_rule(
    body: CreateAclRuleRequest,
    store: InMemoryAclRuleStore = Depends(acl_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rule = AclRule(
        rule_id=str(uuid4()),
        connection_id=body.connection_id,
        workflow_types=tuple(body.workflow_types),
        project_id=body.project_id,
        effect=body.effect,
    )
    return await store.add(rule)


@router.get("/workflow-acl/rules")
async def list_acl_rules(
    store: InMemoryAclRuleStore = Depends(acl_rule_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.delete("/workflow-acl/rules/{rule_id}", status_code=204)
async def delete_acl_rule(
    rule_id: str,
    store: InMemoryAclRuleStore = Depends(acl_rule_store_provider),  # noqa: B008
) -> None:
    removed = await store.remove(rule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="ACL rule not found")


@router.post("/workflow-acl/check")
async def check_acl(
    body: AclCheckRequest,
    store: InMemoryAclRuleStore = Depends(acl_rule_store_provider),  # noqa: B008
) -> AclCheckResult:
    allowed, reason = store.check(
        connection_id=body.connection_id,
        workflow_type=body.workflow_type,
        project_id=body.project_id,
    )
    return AclCheckResult(allowed=allowed, reason=reason)
