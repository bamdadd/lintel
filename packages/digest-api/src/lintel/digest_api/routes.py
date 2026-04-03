"""Digest CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.digest_api.types import Digest, DigestConfig
from lintel.domain.events import DigestConfigCreated, DigestConfigUpdated, DigestCreated

if TYPE_CHECKING:
    from lintel.digest_api.store import InMemoryDigestConfigStore, InMemoryDigestStore

router = APIRouter()

digest_store_provider: StoreProvider = StoreProvider()
digest_config_store_provider: StoreProvider = StoreProvider()


# ---- Request models ----


class CreateDigestRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    team_id: str
    period_start: datetime
    period_end: datetime
    summary: str
    metrics: dict[str, object] = {}
    highlights: list[str] = []


class CreateDigestConfigRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    schedule: str = "weekly"
    recipients: list[str] = []
    enabled: bool = True


class UpdateDigestConfigRequest(BaseModel):
    schedule: str | None = None
    recipients: list[str] | None = None
    enabled: bool | None = None


# ---- Helpers ----


def _digest_to_dict(d: Digest) -> dict[str, Any]:
    data = asdict(d)
    data["period_start"] = d.period_start.isoformat()
    data["period_end"] = d.period_end.isoformat()
    data["created_at"] = d.created_at.isoformat()
    return data


def _config_to_dict(c: DigestConfig) -> dict[str, Any]:
    data = asdict(c)
    data["recipients"] = list(c.recipients)
    return data


# ---- Digest routes ----


@router.post("/digests", status_code=201)
async def create_digest(
    body: CreateDigestRequest,
    request: Request,
    store: InMemoryDigestStore = Depends(digest_store_provider),  # noqa: B008
) -> dict[str, Any]:
    digest = Digest(
        id=body.id,
        project_id=body.project_id,
        team_id=body.team_id,
        period_start=body.period_start,
        period_end=body.period_end,
        summary=body.summary,
        metrics=body.metrics,
        highlights=body.highlights,
    )
    await store.add(digest)
    await dispatch_event(
        request,
        DigestCreated(payload={"resource_id": body.id, "project_id": body.project_id}),
        stream_id=f"digest:{body.id}",
    )
    return _digest_to_dict(digest)


@router.get("/digests")
async def list_digests(
    store: InMemoryDigestStore = Depends(digest_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    items = await store.list_all()
    return [_digest_to_dict(d) for d in items]


@router.get("/digests/{digest_id}")
async def get_digest(
    digest_id: str,
    store: InMemoryDigestStore = Depends(digest_store_provider),  # noqa: B008
) -> dict[str, Any]:
    digest = await store.get(digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return _digest_to_dict(digest)


@router.delete("/digests/{digest_id}", status_code=204)
async def delete_digest(
    digest_id: str,
    store: InMemoryDigestStore = Depends(digest_store_provider),  # noqa: B008
) -> None:
    digest = await store.get(digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    await store.remove(digest_id)


# ---- DigestConfig routes ----


@router.post("/digest-configs", status_code=201)
async def create_digest_config(
    body: CreateDigestConfigRequest,
    request: Request,
    store: InMemoryDigestConfigStore = Depends(digest_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = DigestConfig(
        id=body.id,
        project_id=body.project_id,
        schedule=body.schedule,
        recipients=tuple(body.recipients),
        enabled=body.enabled,
    )
    await store.add(config)
    await dispatch_event(
        request,
        DigestConfigCreated(
            payload={"resource_id": body.id, "project_id": body.project_id},
        ),
        stream_id=f"digest-config:{body.id}",
    )
    return _config_to_dict(config)


@router.get("/digest-configs")
async def list_digest_configs(
    store: InMemoryDigestConfigStore = Depends(digest_config_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    items = await store.list_all()
    return [_config_to_dict(c) for c in items]


@router.get("/digest-configs/{config_id}")
async def get_digest_config(
    config_id: str,
    store: InMemoryDigestConfigStore = Depends(digest_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await store.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Digest config not found")
    return _config_to_dict(config)


@router.patch("/digest-configs/{config_id}")
async def update_digest_config(
    config_id: str,
    body: UpdateDigestConfigRequest,
    request: Request,
    store: InMemoryDigestConfigStore = Depends(digest_config_store_provider),  # noqa: B008
) -> dict[str, Any]:
    config = await store.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Digest config not found")
    updates = body.model_dump(exclude_none=True)
    data = asdict(config)
    if "recipients" in updates:
        updates["recipients"] = tuple(updates["recipients"])
    updated = DigestConfig(**{**data, **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        DigestConfigUpdated(
            payload={"resource_id": config_id, "fields": list(updates.keys())},
        ),
        stream_id=f"digest-config:{config_id}",
    )
    return _config_to_dict(updated)


@router.delete("/digest-configs/{config_id}", status_code=204)
async def delete_digest_config(
    config_id: str,
    store: InMemoryDigestConfigStore = Depends(digest_config_store_provider),  # noqa: B008
) -> None:
    config = await store.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Digest config not found")
    await store.remove(config_id)
