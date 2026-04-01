"""Notification preference CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    NotificationPreferenceCreated,
    NotificationPreferenceUpdated,
)
from lintel.domain.notifications.notification_preference import NotificationPreference
from lintel.domain.types import NotificationChannel

if TYPE_CHECKING:
    from lintel.notifications_api.preference_store import NotificationPreferenceStore

router = APIRouter()

notification_preference_store_provider: StoreProvider = StoreProvider()


class CreateNotificationPreferenceRequest(BaseModel):
    preference_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    event_type: str
    channel: NotificationChannel = NotificationChannel.SLACK
    enabled: bool = True


class UpdateNotificationPreferenceRequest(BaseModel):
    enabled: bool | None = None


@router.post("/notifications/preferences", status_code=201)
async def create_notification_preference(
    body: CreateNotificationPreferenceRequest,
    request: Request,
    store: NotificationPreferenceStore = Depends(  # noqa: B008
        notification_preference_store_provider,
    ),
) -> dict[str, Any]:
    pref = NotificationPreference(
        preference_id=body.preference_id,
        user_id=body.user_id,
        event_type=body.event_type,
        channel=body.channel,
        enabled=body.enabled,
    )
    await store.add(pref)
    await dispatch_event(
        request,
        NotificationPreferenceCreated(
            payload={"resource_id": pref.preference_id, "user_id": pref.user_id},
        ),
        stream_id=f"notification_preference:{pref.preference_id}",
    )
    return asdict(pref)


@router.get("/notifications/preferences")
async def list_notification_preferences(
    store: NotificationPreferenceStore = Depends(  # noqa: B008
        notification_preference_store_provider,
    ),
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    prefs = await store.list_all(user_id=user_id)
    return [asdict(p) for p in prefs]


@router.patch("/notifications/preferences/{preference_id}")
async def update_notification_preference(
    preference_id: str,
    body: UpdateNotificationPreferenceRequest,
    request: Request,
    store: NotificationPreferenceStore = Depends(  # noqa: B008
        notification_preference_store_provider,
    ),
) -> dict[str, Any]:
    pref = await store.get(preference_id)
    if pref is None:
        raise HTTPException(status_code=404, detail="Notification preference not found")
    updates = body.model_dump(exclude_none=True)
    updated = NotificationPreference(**{**asdict(pref), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        NotificationPreferenceUpdated(
            payload={"resource_id": preference_id},
        ),
        stream_id=f"notification_preference:{preference_id}",
    )
    return asdict(updated)
