"""Guardrail rule CRUD endpoints (GRD-7)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore  # noqa: TC001

router = APIRouter()

guardrail_rule_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class _GuardrailAction(StrEnum):
    """Guardrail action choices for Pydantic schemas."""

    WARN = "WARN"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class CreateGuardrailRuleRequest(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    event_type: str
    condition: str
    action: _GuardrailAction
    threshold: float | None = None
    cooldown_seconds: int = 0
    enabled: bool = True


class UpdateGuardrailRuleRequest(BaseModel):
    action: _GuardrailAction | None = None
    threshold: float | None = None
    cooldown_seconds: int | None = None
    enabled: bool | None = None


@router.get("/guardrail-rules")
async def list_guardrail_rules(
    store: Annotated[ComplianceStore, Depends(guardrail_rule_store_provider)],
    enabled: bool | None = None,
    is_default: bool | None = None,
) -> list[dict[str, Any]]:
    """List all guardrail rules, optionally filtered."""
    rules = await store.list_all()
    if enabled is not None:
        rules = [r for r in rules if r.get("enabled") == enabled]
    if is_default is not None:
        rules = [r for r in rules if r.get("is_default") == is_default]
    return rules


@router.get("/guardrail-rules/{rule_id}")
async def get_guardrail_rule(
    rule_id: str,
    store: Annotated[ComplianceStore, Depends(guardrail_rule_store_provider)],
) -> dict[str, Any]:
    """Get a single guardrail rule by ID."""
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Guardrail rule not found")
    return rule


@router.post("/guardrail-rules", status_code=201)
async def create_guardrail_rule(
    request: Request,
    body: CreateGuardrailRuleRequest,
    store: Annotated[ComplianceStore, Depends(guardrail_rule_store_provider)],
) -> dict[str, Any]:
    """Create a custom guardrail rule."""
    from lintel.domain.events import GuardrailTriggered
    from lintel.domain.guardrails.models import GuardrailRule

    existing = await store.get(body.rule_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Rule already exists")

    rule = GuardrailRule(
        rule_id=body.rule_id,
        name=body.name,
        event_type=body.event_type,
        condition=body.condition,
        action=body.action,
        threshold=body.threshold,
        cooldown_seconds=body.cooldown_seconds,
        is_default=False,
        enabled=body.enabled,
    )
    result = await store.add(rule)
    await dispatch_event(
        request,
        GuardrailTriggered(
            payload={
                "rule_id": body.rule_id,
                "name": body.name,
                "action": "created",
            },
        ),
        stream_id=f"guardrail_rule:{body.rule_id}",
    )
    return result


@router.put("/guardrail-rules/{rule_id}")
async def update_guardrail_rule(
    rule_id: str,
    body: UpdateGuardrailRuleRequest,
    store: Annotated[ComplianceStore, Depends(guardrail_rule_store_provider)],
) -> dict[str, Any]:
    """Update a guardrail rule's mutable fields."""
    existing = await store.get(rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Guardrail rule not found")

    updates: dict[str, Any] = {}
    if body.action is not None:
        updates["action"] = body.action.value
    if body.threshold is not None:
        updates["threshold"] = body.threshold
    if body.cooldown_seconds is not None:
        updates["cooldown_seconds"] = body.cooldown_seconds
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    if not updates:
        return existing

    result = await store.update(rule_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Guardrail rule not found")
    return result


@router.delete("/guardrail-rules/{rule_id}", status_code=204)
async def delete_guardrail_rule(
    rule_id: str,
    store: Annotated[ComplianceStore, Depends(guardrail_rule_store_provider)],
) -> None:
    """Delete a guardrail rule. Default rules cannot be deleted."""
    existing = await store.get(rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Guardrail rule not found")
    if existing.get("is_default", False):
        raise HTTPException(
            status_code=403,
            detail="Default guardrail rules cannot be deleted",
        )
    await store.remove(rule_id)
