"""Privacy controls CRUD endpoints (REQ-008)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    MetricVisibilityRemoved,
    MetricVisibilitySet,
    PrivacyPreferenceUpdated,
)
from lintel.domain.types import MetricVisibility, PrivacyLevel, PrivacyPreference
from lintel.privacy_controls_api.store import (
    InMemoryPreferenceStore,  # noqa: TC001
    InMemoryVisibilityStore,  # noqa: TC001
)

router = APIRouter()

visibility_store_provider: StoreProvider[InMemoryVisibilityStore] = StoreProvider()
preference_store_provider: StoreProvider[InMemoryPreferenceStore] = StoreProvider()


# --- Request models ---


class CreateVisibilityRequest(BaseModel):
    user_id: str
    metric_type: str
    privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
    allowed_viewers: list[str] = Field(default_factory=list)


class UpdateVisibilityRequest(BaseModel):
    privacy_level: PrivacyLevel | None = None
    allowed_viewers: list[str] | None = None


class PutPreferenceRequest(BaseModel):
    default_privacy_level: PrivacyLevel = PrivacyLevel.PRIVATE
    opt_out_metrics: list[str] = Field(default_factory=list)


# --- Visibility endpoints ---


@router.post("/privacy/visibility", status_code=201)
async def create_visibility(
    request: Request,
    body: CreateVisibilityRequest,
    store: Annotated[InMemoryVisibilityStore, Depends(visibility_store_provider)],
) -> dict[str, Any]:
    item = MetricVisibility(
        visibility_id=str(uuid4()),
        user_id=body.user_id,
        metric_type=body.metric_type,
        privacy_level=body.privacy_level,
        allowed_viewers=tuple(body.allowed_viewers),
    )
    result = await store.add(item)
    await dispatch_event(
        request,
        MetricVisibilitySet(
            payload={
                "resource_id": item.visibility_id,
                "user_id": body.user_id,
                "metric_type": body.metric_type,
                "privacy_level": body.privacy_level.value,
            },
        ),
        stream_id=f"privacy:{item.visibility_id}",
    )
    return result


@router.get("/privacy/visibility")
async def list_visibility(
    store: Annotated[InMemoryVisibilityStore, Depends(visibility_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/privacy/visibility/{visibility_id}")
async def get_visibility(
    visibility_id: str,
    store: Annotated[InMemoryVisibilityStore, Depends(visibility_store_provider)],
) -> dict[str, Any]:
    item = await store.get(visibility_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Metric visibility not found")
    return item


@router.patch("/privacy/visibility/{visibility_id}")
async def update_visibility(
    request: Request,
    visibility_id: str,
    body: UpdateVisibilityRequest,
    store: Annotated[InMemoryVisibilityStore, Depends(visibility_store_provider)],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if body.privacy_level is not None:
        updates["privacy_level"] = body.privacy_level
    if body.allowed_viewers is not None:
        updates["allowed_viewers"] = body.allowed_viewers
    if not updates:
        existing = await store.get(visibility_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Metric visibility not found")
        return existing
    result = await store.update(visibility_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Metric visibility not found")
    await dispatch_event(
        request,
        MetricVisibilitySet(
            payload={"resource_id": visibility_id, **updates},
        ),
        stream_id=f"privacy:{visibility_id}",
    )
    return result


@router.delete("/privacy/visibility/{visibility_id}", status_code=204)
async def delete_visibility(
    request: Request,
    visibility_id: str,
    store: Annotated[InMemoryVisibilityStore, Depends(visibility_store_provider)],
) -> None:
    if not await store.remove(visibility_id):
        raise HTTPException(status_code=404, detail="Metric visibility not found")
    await dispatch_event(
        request,
        MetricVisibilityRemoved(payload={"resource_id": visibility_id}),
        stream_id=f"privacy:{visibility_id}",
    )


# --- Preference endpoints ---


@router.get("/privacy/preferences/{user_id}")
async def get_preference(
    user_id: str,
    store: Annotated[InMemoryPreferenceStore, Depends(preference_store_provider)],
) -> dict[str, Any]:
    item = await store.get(user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Privacy preference not found")
    return item


@router.put("/privacy/preferences/{user_id}")
async def put_preference(
    request: Request,
    user_id: str,
    body: PutPreferenceRequest,
    store: Annotated[InMemoryPreferenceStore, Depends(preference_store_provider)],
) -> dict[str, Any]:
    item = PrivacyPreference(
        preference_id=str(uuid4()),
        user_id=user_id,
        default_privacy_level=body.default_privacy_level,
        opt_out_metrics=tuple(body.opt_out_metrics),
    )
    result = await store.put(item)
    await dispatch_event(
        request,
        PrivacyPreferenceUpdated(
            payload={
                "resource_id": item.preference_id,
                "user_id": user_id,
                "default_privacy_level": body.default_privacy_level.value,
            },
        ),
        stream_id=f"privacy-pref:{user_id}",
    )
    return result
