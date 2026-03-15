"""Notification rule CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    NotificationRuleCreated,
    NotificationRuleRemoved,
    NotificationRuleUpdated,
)
from lintel.domain.types import NotificationChannel, NotificationRule
from lintel.notifications_api.store import NotificationRuleStore

router = APIRouter()

notification_rule_store_provider: StoreProvider = StoreProvider()


def _rule_to_dict(rule: NotificationRule) -> dict[str, Any]:
    data = asdict(rule)
    data["event_types"] = list(rule.event_types)
    return data


class CreateNotificationRuleRequest(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    event_types: list[str] = []
    channel: NotificationChannel = NotificationChannel.SLACK
    target: str = ""
    enabled: bool = True


class UpdateNotificationRuleRequest(BaseModel):
    enabled: bool | None = None
    target: str | None = None


@router.post("/notifications/rules", status_code=201)
async def create_notification_rule(
    body: CreateNotificationRuleRequest,
    request: Request,
    store: NotificationRuleStore = Depends(notification_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.rule_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Notification rule already exists")
    rule = NotificationRule(
        rule_id=body.rule_id,
        project_id=body.project_id,
        event_types=tuple(body.event_types),
        channel=body.channel,
        target=body.target,
        enabled=body.enabled,
    )
    await store.add(rule)
    await dispatch_event(
        request,
        NotificationRuleCreated(payload={"resource_id": rule.rule_id}),
        stream_id=f"notification_rule:{rule.rule_id}",
    )
    return _rule_to_dict(rule)


@router.get("/notifications/rules")
async def list_notification_rules(
    store: NotificationRuleStore = Depends(notification_rule_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    rules = await store.list_all(project_id=project_id)
    return [_rule_to_dict(r) for r in rules]


@router.get("/notifications/rules/{rule_id}")
async def get_notification_rule(
    rule_id: str,
    store: NotificationRuleStore = Depends(notification_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return _rule_to_dict(rule)


@router.patch("/notifications/rules/{rule_id}")
async def update_notification_rule(
    rule_id: str,
    body: UpdateNotificationRuleRequest,
    request: Request,
    store: NotificationRuleStore = Depends(notification_rule_store_provider),  # noqa: B008
) -> dict[str, Any]:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    updates = body.model_dump(exclude_none=True)
    updated = NotificationRule(**{**asdict(rule), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        NotificationRuleUpdated(payload={"resource_id": rule_id}),
        stream_id=f"notification_rule:{rule_id}",
    )
    return _rule_to_dict(updated)


@router.delete("/notifications/rules/{rule_id}", status_code=204)
async def delete_notification_rule(
    rule_id: str,
    request: Request,
    store: NotificationRuleStore = Depends(notification_rule_store_provider),  # noqa: B008
) -> None:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    await store.remove(rule_id)
    await dispatch_event(
        request,
        NotificationRuleRemoved(payload={"resource_id": rule_id}),
        stream_id=f"notification_rule:{rule_id}",
    )
