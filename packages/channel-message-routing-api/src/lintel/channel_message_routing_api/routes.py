"""Channel message routing CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.channel_message_routing_api.router_engine import ChannelRouter
from lintel.channel_message_routing_api.store import InMemoryRoutingRuleStore, RoutingRule

router = APIRouter()

routing_rule_store_provider: StoreProvider[InMemoryRoutingRuleStore] = StoreProvider()

_channel_router = ChannelRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRoutingRuleRequest(BaseModel):
    rule_id: str | None = None
    connection_id: str
    channel_pattern: str = "*"
    message_pattern: str = ""
    workflow_definition_id: str
    priority: int = 0


class ResolveRequest(BaseModel):
    connection_id: str
    channel: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/channel-routing/rules", status_code=201)
async def create_routing_rule(
    body: CreateRoutingRuleRequest,
    store: InMemoryRoutingRuleStore = Depends(routing_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rule = RoutingRule(
        connection_id=body.connection_id,
        channel_pattern=body.channel_pattern,
        message_pattern=body.message_pattern,
        workflow_definition_id=body.workflow_definition_id,
        priority=body.priority,
    )
    if body.rule_id is not None:
        rule.rule_id = body.rule_id
    try:
        await store.add(rule)
    except KeyError:
        raise HTTPException(status_code=409, detail="Routing rule already exists")  # noqa: B904
    return asdict(rule)


@router.get("/channel-routing/rules")
async def list_routing_rules(
    connection_id: str | None = None,
    store: InMemoryRoutingRuleStore = Depends(routing_rule_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    rules = await store.list_all(connection_id=connection_id)
    return [asdict(r) for r in rules]


@router.get("/channel-routing/rules/{rule_id}")
async def get_routing_rule(
    rule_id: str,
    store: InMemoryRoutingRuleStore = Depends(routing_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    return asdict(rule)


@router.delete("/channel-routing/rules/{rule_id}", status_code=204)
async def delete_routing_rule(
    rule_id: str,
    store: InMemoryRoutingRuleStore = Depends(routing_rule_store_provider),  # noqa: B008
) -> None:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    await store.remove(rule_id)


@router.post("/channel-routing/resolve")
async def resolve_routing(
    body: ResolveRequest,
    store: InMemoryRoutingRuleStore = Depends(routing_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rules = await store.list_all(connection_id=body.connection_id)
    match = _channel_router.resolve(
        rules=rules,
        connection_id=body.connection_id,
        channel=body.channel,
        message=body.message,
    )
    return {"match": asdict(match) if match else None}
