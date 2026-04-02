"""Coding Rules CRUD endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.coding_rules_api.store import (  # noqa: TC001
    InMemoryCodingRuleStore,
    InMemoryRuleViolationStore,
)
from lintel.domain.events import (
    CodingRuleCreated,
    CodingRuleRemoved,
    CodingRuleUpdated,
    RuleViolationDetected,
    RuleViolationResolved,
)
from lintel.domain.types import CodingRule, RuleScope, RuleSeverity

router = APIRouter()

coding_rule_store_provider: StoreProvider[InMemoryCodingRuleStore] = StoreProvider()
violation_store_provider: StoreProvider[InMemoryRuleViolationStore] = StoreProvider()


# --- Request / Response models ---


class ScopeModel(BaseModel):
    directory_pattern: str = "**"
    file_pattern: str = "*"
    language: str = ""


class CreateCodingRuleRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""
    severity: RuleSeverity = RuleSeverity.WARNING
    scope: ScopeModel = Field(default_factory=ScopeModel)
    active: bool = True
    project_id: str = ""


class UpdateCodingRuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    severity: RuleSeverity | None = None
    scope: ScopeModel | None = None
    active: bool | None = None
    project_id: str | None = None


class CreateViolationRequest(BaseModel):
    rule_id: str
    pipeline_run_id: str = ""
    file_path: str = ""
    line_number: int | None = None
    message: str = ""
    agent_id: str = ""


class UpdateViolationRequest(BaseModel):
    resolved: bool | None = None
    message: str | None = None


# --- Rule endpoints ---


@router.post("/coding-rules", status_code=201)
async def create_coding_rule(
    request: Request,
    body: CreateCodingRuleRequest,
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
) -> dict[str, Any]:
    rule_id = str(uuid4())
    rule = CodingRule(
        rule_id=rule_id,
        name=body.name,
        description=body.description,
        content=body.content,
        severity=body.severity,
        scope=RuleScope(
            directory_pattern=body.scope.directory_pattern,
            file_pattern=body.scope.file_pattern,
            language=body.scope.language,
        ),
        active=body.active,
        project_id=body.project_id,
    )
    result = await store.add(rule)
    await dispatch_event(
        request,
        CodingRuleCreated(
            payload={"resource_id": rule_id, "name": body.name},
        ),
        stream_id=f"coding-rule:{rule_id}",
    )
    return result


@router.get("/coding-rules")
async def list_coding_rules(
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/coding-rules/match")
async def match_coding_rules(
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
    path: Annotated[str, Query()],
) -> list[dict[str, Any]]:
    return store.match_path(path)


# --- Violation endpoints (must be before {rule_id} to avoid path conflicts) ---


@router.get("/coding-rules/violations")
async def list_violations(
    vstore: Annotated[InMemoryRuleViolationStore, Depends(violation_store_provider)],
    rule_id: Annotated[str | None, Query()] = None,
    pipeline_run_id: Annotated[str | None, Query()] = None,
    resolved: Annotated[bool | None, Query()] = None,
) -> list[dict[str, Any]]:
    return await vstore.list_all(
        rule_id=rule_id,
        pipeline_run_id=pipeline_run_id,
        resolved=resolved,
    )


@router.post("/coding-rules/violations", status_code=201)
async def create_violation(
    request: Request,
    body: CreateViolationRequest,
    vstore: Annotated[InMemoryRuleViolationStore, Depends(violation_store_provider)],
) -> dict[str, Any]:
    from lintel.domain.types import RuleViolation

    violation_id = str(uuid4())
    violation = RuleViolation(
        violation_id=violation_id,
        rule_id=body.rule_id,
        pipeline_run_id=body.pipeline_run_id,
        file_path=body.file_path,
        line_number=body.line_number,
        message=body.message,
        agent_id=body.agent_id,
    )
    result = await vstore.add(violation)
    await dispatch_event(
        request,
        RuleViolationDetected(
            payload={
                "violation_id": violation_id,
                "rule_id": body.rule_id,
                "file_path": body.file_path,
            },
        ),
        stream_id=f"coding-rule-violation:{violation_id}",
    )
    return result


@router.patch("/coding-rules/violations/{violation_id}")
async def update_violation(
    request: Request,
    violation_id: str,
    body: UpdateViolationRequest,
    vstore: Annotated[InMemoryRuleViolationStore, Depends(violation_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await vstore.update(violation_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    if updates.get("resolved") is True:
        await dispatch_event(
            request,
            RuleViolationResolved(
                payload={"violation_id": violation_id},
            ),
            stream_id=f"coding-rule-violation:{violation_id}",
        )
    return result


# --- Rule detail endpoints ---


@router.get("/coding-rules/{rule_id}")
async def get_coding_rule(
    rule_id: str,
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
) -> dict[str, Any]:
    item = await store.get(rule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Coding rule not found")
    return item


@router.patch("/coding-rules/{rule_id}")
async def update_coding_rule(
    request: Request,
    rule_id: str,
    body: UpdateCodingRuleRequest,
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "scope" in updates:
        scope_data = updates.pop("scope")
        updates["scope"] = RuleScope(
            directory_pattern=scope_data.get("directory_pattern", "**"),
            file_pattern=scope_data.get("file_pattern", "*"),
            language=scope_data.get("language", ""),
        )
    result = await store.update(rule_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Coding rule not found")
    await dispatch_event(
        request,
        CodingRuleUpdated(payload={"resource_id": rule_id}),
        stream_id=f"coding-rule:{rule_id}",
    )
    return result


@router.delete("/coding-rules/{rule_id}", status_code=204)
async def delete_coding_rule(
    request: Request,
    rule_id: str,
    store: Annotated[InMemoryCodingRuleStore, Depends(coding_rule_store_provider)],
) -> None:
    if not await store.remove(rule_id):
        raise HTTPException(status_code=404, detail="Coding rule not found")
    await dispatch_event(
        request,
        CodingRuleRemoved(payload={"resource_id": rule_id}),
        stream_id=f"coding-rule:{rule_id}",
    )
