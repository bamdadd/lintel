"""Notification rule CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.contracts.types import NotificationChannel, NotificationRule

router = APIRouter()


class NotificationRuleStore:
    """In-memory store for notification rules."""

    def __init__(self) -> None:
        self._rules: dict[str, NotificationRule] = {}

    async def add(self, rule: NotificationRule) -> None:
        self._rules[rule.rule_id] = rule

    async def get(self, rule_id: str) -> NotificationRule | None:
        return self._rules.get(rule_id)

    async def list_all(self, *, project_id: str | None = None) -> list[NotificationRule]:
        rules = list(self._rules.values())
        if project_id is not None:
            rules = [r for r in rules if r.project_id == project_id]
        return rules

    async def update(self, rule: NotificationRule) -> None:
        self._rules[rule.rule_id] = rule

    async def remove(self, rule_id: str) -> None:
        del self._rules[rule_id]


def get_notification_rule_store(request: Request) -> NotificationRuleStore:
    """Get notification rule store from app state."""
    return request.app.state.notification_rule_store  # type: ignore[no-any-return]


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
    store: Annotated[NotificationRuleStore, Depends(get_notification_rule_store)],
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
    return _rule_to_dict(rule)


@router.get("/notifications/rules")
async def list_notification_rules(
    store: Annotated[NotificationRuleStore, Depends(get_notification_rule_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    rules = await store.list_all(project_id=project_id)
    return [_rule_to_dict(r) for r in rules]


@router.get("/notifications/rules/{rule_id}")
async def get_notification_rule(
    rule_id: str,
    store: Annotated[NotificationRuleStore, Depends(get_notification_rule_store)],
) -> dict[str, Any]:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return _rule_to_dict(rule)


@router.patch("/notifications/rules/{rule_id}")
async def update_notification_rule(
    rule_id: str,
    body: UpdateNotificationRuleRequest,
    store: Annotated[NotificationRuleStore, Depends(get_notification_rule_store)],
) -> dict[str, Any]:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    updates = body.model_dump(exclude_none=True)
    updated = NotificationRule(**{**asdict(rule), **updates})
    await store.update(updated)
    return _rule_to_dict(updated)


@router.delete("/notifications/rules/{rule_id}", status_code=204)
async def delete_notification_rule(
    rule_id: str,
    store: Annotated[NotificationRuleStore, Depends(get_notification_rule_store)],
) -> None:
    rule = await store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    await store.remove(rule_id)
