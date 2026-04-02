"""Playbook REST API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import PlaybookCreated
from lintel.domain.types import Playbook

if TYPE_CHECKING:
    from lintel.playbooks_api.store import PlaybookStore

router = APIRouter()

playbook_store_provider: StoreProvider[PlaybookStore] = StoreProvider()


class CreatePlaybookRequest(BaseModel):
    playbook_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    strategy: str = ""
    source_synthesis_ids: list[str] = Field(default_factory=list)
    created_at: str = ""


@router.post("/playbooks", status_code=201)
async def create_playbook(
    request: Request,
    body: CreatePlaybookRequest,
    store: PlaybookStore = Depends(playbook_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.playbook_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Playbook already exists")
    playbook = Playbook(
        playbook_id=body.playbook_id,
        title=body.title,
        strategy=body.strategy,
        source_synthesis_ids=tuple(body.source_synthesis_ids),
        created_at=body.created_at,
    )
    result = await store.add(playbook)
    await dispatch_event(
        request,
        PlaybookCreated(
            payload={"resource_id": body.playbook_id, "title": body.title},
        ),
        stream_id=f"playbook:{body.playbook_id}",
    )
    return result


@router.get("/playbooks/{playbook_id}")
async def get_playbook(
    playbook_id: str,
    store: PlaybookStore = Depends(playbook_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(playbook_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return item


@router.get("/playbooks")
async def list_playbooks(
    store: PlaybookStore = Depends(playbook_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all()
