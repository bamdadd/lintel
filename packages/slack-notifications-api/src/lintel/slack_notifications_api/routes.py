"""Slack notification template and record CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    SlackNotificationSent,
    SlackNotificationTemplateCreated,
    SlackNotificationTemplateUpdated,
)
from lintel.domain.types import (
    SlackNotificationRecord,
    SlackNotificationStatus,
    SlackNotificationTemplate,
)

if TYPE_CHECKING:
    from lintel.slack_notifications_api.store import (
        InMemorySlackNotificationRecordStore,
        InMemorySlackNotificationTemplateStore,
    )

router = APIRouter()

template_store_provider: StoreProvider[Any] = StoreProvider()
record_store_provider: StoreProvider[Any] = StoreProvider()


# --- Request/Response models ---


class CreateTemplateRequest(BaseModel):
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    stage_name: str
    block_kit_template: str = ""
    active: bool = True
    project_id: str = ""


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    stage_name: str | None = None
    block_kit_template: str | None = None
    active: bool | None = None
    project_id: str | None = None


class NotifyRequest(BaseModel):
    pipeline_run_id: str
    stage_name: str
    slack_channel_id: str
    slack_thread_ts: str


# --- Helpers ---


def _template_to_dict(t: SlackNotificationTemplate) -> dict[str, Any]:
    return asdict(t)


def _record_to_dict(r: SlackNotificationRecord) -> dict[str, Any]:
    return asdict(r)


# --- Template endpoints ---


@router.post("/slack/notification-templates", status_code=201)
async def create_template(
    body: CreateTemplateRequest,
    request: Request,
    store: InMemorySlackNotificationTemplateStore = Depends(template_store_provider),  # noqa: B008
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    template = SlackNotificationTemplate(
        template_id=body.template_id,
        name=body.name,
        stage_name=body.stage_name,
        block_kit_template=body.block_kit_template,
        active=body.active,
        project_id=body.project_id,
        created_at=now,
        updated_at=now,
    )
    await store.add(template)
    await dispatch_event(
        request,
        SlackNotificationTemplateCreated(
            payload={"resource_id": body.template_id, "name": body.name},
        ),
        stream_id=f"slack-notification-template:{body.template_id}",
    )
    return _template_to_dict(template)


@router.get("/slack/notification-templates")
async def list_templates(
    store: InMemorySlackNotificationTemplateStore = Depends(template_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    items = await store.list_all()
    return [_template_to_dict(t) for t in items]


@router.get("/slack/notification-templates/{template_id}")
async def get_template(
    template_id: str,
    store: InMemorySlackNotificationTemplateStore = Depends(template_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_dict(item)


@router.patch("/slack/notification-templates/{template_id}")
async def update_template(
    template_id: str,
    body: UpdateTemplateRequest,
    request: Request,
    store: InMemorySlackNotificationTemplateStore = Depends(template_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(template_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Template not found")
    updates = body.model_dump(exclude_none=True)
    now = datetime.now(UTC).isoformat()
    updated = SlackNotificationTemplate(
        **{**asdict(existing), **updates, "updated_at": now},
    )
    await store.update(updated)
    await dispatch_event(
        request,
        SlackNotificationTemplateUpdated(
            payload={"resource_id": template_id, "fields": list(updates.keys())},
        ),
        stream_id=f"slack-notification-template:{template_id}",
    )
    return _template_to_dict(updated)


@router.delete("/slack/notification-templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    store: InMemorySlackNotificationTemplateStore = Depends(template_store_provider),  # noqa: B008
) -> None:
    existing = await store.get(template_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await store.remove(template_id)


# --- Record endpoints ---


@router.get("/slack/notification-records")
async def list_records(
    pipeline_run_id: str | None = None,
    stage_name: str | None = None,
    store: InMemorySlackNotificationRecordStore = Depends(record_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if pipeline_run_id:
        items = await store.list_by_pipeline(pipeline_run_id)
    elif stage_name:
        items = await store.list_by_stage(stage_name)
    else:
        items = await store.list_all()
    return [_record_to_dict(r) for r in items]


# --- Manual notify endpoint ---


@router.post("/slack/notify", status_code=201)
async def notify(
    body: NotifyRequest,
    request: Request,
    record_store: InMemorySlackNotificationRecordStore = Depends(record_store_provider),  # noqa: B008
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    record_id = str(uuid4())
    record = SlackNotificationRecord(
        record_id=record_id,
        pipeline_run_id=body.pipeline_run_id,
        stage_name=body.stage_name,
        slack_channel_id=body.slack_channel_id,
        slack_thread_ts=body.slack_thread_ts,
        slack_message_ts="",
        status=SlackNotificationStatus.SENT,
        created_at=now,
    )
    await record_store.add(record)
    await dispatch_event(
        request,
        SlackNotificationSent(
            payload={
                "record_id": record_id,
                "pipeline_run_id": body.pipeline_run_id,
                "stage_name": body.stage_name,
            },
        ),
        stream_id=f"slack-notification:{record_id}",
    )
    return _record_to_dict(record)
