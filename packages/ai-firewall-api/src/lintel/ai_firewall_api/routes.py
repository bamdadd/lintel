"""AI Firewall CRUD endpoints (REQ-025)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.ai_firewall_api.store import (  # noqa: TC001
    InMemoryFirewallLogStore,
    InMemoryFirewallRuleStore,
)
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    AgentRequestAllowed,
    AgentRequestBlocked,
    FirewallRuleCreated,
    FirewallRuleRemoved,
    FirewallRuleUpdated,
)
from lintel.domain.types import FirewallAction, FirewallLogEntry, FirewallRule

router = APIRouter()

firewall_rule_store_provider: StoreProvider[InMemoryFirewallRuleStore] = StoreProvider()
firewall_log_store_provider: StoreProvider[InMemoryFirewallLogStore] = StoreProvider()


# --- Request / Response models ---


class CreateFirewallRuleRequest(BaseModel):
    name: str
    description: str = ""
    pattern: str
    action: FirewallAction = FirewallAction.DENY
    agent_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0)
    active: bool = True
    project_id: str = ""


class UpdateFirewallRuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    pattern: str | None = None
    action: FirewallAction | None = None
    agent_roles: list[str] | None = None
    priority: int | None = Field(default=None, ge=0)
    active: bool | None = None
    project_id: str | None = None


class CheckUrlRequest(BaseModel):
    url: str
    agent_id: str
    agent_role: str = ""


class CheckUrlResponse(BaseModel):
    url: str
    action: FirewallAction
    blocked: bool
    matching_rule_id: str | None = None


# --- Rule endpoints ---


@router.post("/firewall/rules", status_code=201)
async def create_firewall_rule(
    request: Request,
    body: CreateFirewallRuleRequest,
    store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
) -> dict[str, Any]:
    rule_id = str(uuid4())
    rule = FirewallRule(
        rule_id=rule_id,
        name=body.name,
        description=body.description,
        pattern=body.pattern,
        action=body.action,
        agent_roles=tuple(body.agent_roles),
        priority=body.priority,
        active=body.active,
        project_id=body.project_id,
    )
    result = await store.add(rule)
    await dispatch_event(
        request,
        FirewallRuleCreated(
            payload={"resource_id": rule_id, "name": body.name, "pattern": body.pattern},
        ),
        stream_id=f"firewall-rule:{rule_id}",
    )
    return result


@router.get("/firewall/rules")
async def list_firewall_rules(
    store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/firewall/rules/{rule_id}")
async def get_firewall_rule(
    rule_id: str,
    store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
) -> dict[str, Any]:
    item = await store.get(rule_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Firewall rule not found")
    return item


@router.patch("/firewall/rules/{rule_id}")
async def update_firewall_rule(
    request: Request,
    rule_id: str,
    body: UpdateFirewallRuleRequest,
    store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(rule_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Firewall rule not found")
    await dispatch_event(
        request,
        FirewallRuleUpdated(payload={"resource_id": rule_id}),
        stream_id=f"firewall-rule:{rule_id}",
    )
    return result


@router.delete("/firewall/rules/{rule_id}", status_code=204)
async def delete_firewall_rule(
    request: Request,
    rule_id: str,
    store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
) -> None:
    if not await store.remove(rule_id):
        raise HTTPException(status_code=404, detail="Firewall rule not found")
    await dispatch_event(
        request,
        FirewallRuleRemoved(payload={"resource_id": rule_id}),
        stream_id=f"firewall-rule:{rule_id}",
    )


# --- Log endpoints ---


@router.get("/firewall/logs")
async def list_firewall_logs(
    log_store: Annotated[InMemoryFirewallLogStore, Depends(firewall_log_store_provider)],
    agent_id: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    blocked: Annotated[bool | None, Query()] = None,
) -> list[dict[str, Any]]:
    return await log_store.list_all(agent_id=agent_id, action=action, blocked=blocked)


# --- Check endpoint ---


@router.post("/firewall/check")
async def check_url(
    request: Request,
    body: CheckUrlRequest,
    rule_store: Annotated[InMemoryFirewallRuleStore, Depends(firewall_rule_store_provider)],
    log_store: Annotated[InMemoryFirewallLogStore, Depends(firewall_log_store_provider)],
) -> CheckUrlResponse:
    action, matching_rule_id = rule_store.check_url(body.url, body.agent_role)
    is_blocked = action == FirewallAction.DENY

    log_entry = FirewallLogEntry(
        log_id=str(uuid4()),
        rule_id=matching_rule_id or "",
        agent_id=body.agent_id,
        url=body.url,
        action_taken=action,
        blocked=is_blocked,
        project_id="",
    )
    await log_store.add(log_entry)

    if is_blocked:
        await dispatch_event(
            request,
            AgentRequestBlocked(
                payload={
                    "agent_id": body.agent_id,
                    "url": body.url,
                    "rule_id": matching_rule_id or "",
                },
            ),
            stream_id=f"firewall-agent:{body.agent_id}",
        )
    else:
        await dispatch_event(
            request,
            AgentRequestAllowed(
                payload={
                    "agent_id": body.agent_id,
                    "url": body.url,
                    "action": action.value,
                },
            ),
            stream_id=f"firewall-agent:{body.agent_id}",
        )

    return CheckUrlResponse(
        url=body.url,
        action=action,
        blocked=is_blocked,
        matching_rule_id=matching_rule_id,
    )
