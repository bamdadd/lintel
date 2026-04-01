"""Notification template CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import NotificationTemplateCreated
from lintel.domain.notifications.notification_template import NotificationTemplate
from lintel.domain.types import NotificationChannel

if TYPE_CHECKING:
    from lintel.notifications_api.template_store import NotificationTemplateStore

router = APIRouter()

notification_template_store_provider: StoreProvider = StoreProvider()


class CreateNotificationTemplateRequest(BaseModel):
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    channel: NotificationChannel = NotificationChannel.SLACK
    body_template: str
    subject_template: str = ""


@router.post("/notifications/templates", status_code=201)
async def create_notification_template(
    body: CreateNotificationTemplateRequest,
    request: Request,
    store: NotificationTemplateStore = Depends(  # noqa: B008
        notification_template_store_provider,
    ),
) -> dict[str, Any]:
    tpl = NotificationTemplate(
        template_id=body.template_id,
        name=body.name,
        channel=body.channel,
        body_template=body.body_template,
        subject_template=body.subject_template,
    )
    await store.add(tpl)
    await dispatch_event(
        request,
        NotificationTemplateCreated(
            payload={"resource_id": tpl.template_id, "name": tpl.name},
        ),
        stream_id=f"notification_template:{tpl.template_id}",
    )
    return asdict(tpl)


@router.get("/notifications/templates")
async def list_notification_templates(
    store: NotificationTemplateStore = Depends(  # noqa: B008
        notification_template_store_provider,
    ),
) -> list[dict[str, Any]]:
    templates = await store.list_all()
    return [asdict(t) for t in templates]


@router.get("/notifications/templates/{template_id}")
async def get_notification_template(
    template_id: str,
    store: NotificationTemplateStore = Depends(  # noqa: B008
        notification_template_store_provider,
    ),
) -> dict[str, Any]:
    tpl = await store.get(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Notification template not found")
    return asdict(tpl)
