"""Knowledge base CRUD and search endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    KnowledgeEntryCreated,
    KnowledgeEntryRemoved,
    KnowledgeEntryUpdated,
)
from lintel.knowledge_api.types import KnowledgeEntry, SourceType

if TYPE_CHECKING:
    from lintel.knowledge_api.store import InMemoryKnowledgeStore

router = APIRouter()

knowledge_store_provider: StoreProvider[InMemoryKnowledgeStore] = StoreProvider()


class CreateKnowledgeEntryRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    content: str = ""
    source_type: SourceType = SourceType.NOTE
    embedding: list[float] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class UpdateKnowledgeEntryRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    source_type: SourceType | None = None
    embedding: list[float] | None = None
    metadata: dict[str, str] | None = None


class SearchKnowledgeRequest(BaseModel):
    query: str = ""
    query_embedding: list[float] | None = None
    project_id: str | None = None
    limit: int = 10


def _entry_to_dict(entry: KnowledgeEntry) -> dict[str, Any]:
    data = asdict(entry)
    if entry.embedding is not None:
        data["embedding"] = list(entry.embedding)
    return data


@router.post("/knowledge", status_code=201)
async def create_knowledge_entry(
    body: CreateKnowledgeEntryRequest,
    request: Request,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Knowledge entry already exists")
    entry = KnowledgeEntry(
        id=body.id,
        project_id=body.project_id,
        title=body.title,
        content=body.content,
        source_type=body.source_type,
        embedding=tuple(body.embedding) if body.embedding is not None else None,
        metadata=body.metadata,
    )
    await store.add(entry)
    await dispatch_event(
        request,
        KnowledgeEntryCreated(payload={"resource_id": body.id, "title": body.title}),
        stream_id=f"knowledge:{body.id}",
    )
    return _entry_to_dict(entry)


@router.get("/knowledge")
async def list_knowledge_entries(
    project_id: str | None = None,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    entries = await store.list_all(project_id=project_id)
    return [_entry_to_dict(e) for e in entries]


@router.get("/knowledge/{entry_id}")
async def get_knowledge_entry(
    entry_id: str,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> dict[str, Any]:
    entry = await store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return _entry_to_dict(entry)


@router.patch("/knowledge/{entry_id}")
async def update_knowledge_entry(
    entry_id: str,
    body: UpdateKnowledgeEntryRequest,
    request: Request,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> dict[str, Any]:
    entry = await store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    updates = body.model_dump(exclude_none=True)
    data = asdict(entry)
    if "embedding" in updates and updates["embedding"] is not None:
        updates["embedding"] = tuple(updates["embedding"])
    data.update(updates)
    updated = KnowledgeEntry(**data)
    await store.update(updated)
    await dispatch_event(
        request,
        KnowledgeEntryUpdated(payload={"resource_id": entry_id, "fields": list(updates.keys())}),
        stream_id=f"knowledge:{entry_id}",
    )
    return _entry_to_dict(updated)


@router.delete("/knowledge/{entry_id}", status_code=204)
async def delete_knowledge_entry(
    entry_id: str,
    request: Request,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> None:
    entry = await store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    await store.remove(entry_id)
    await dispatch_event(
        request,
        KnowledgeEntryRemoved(payload={"resource_id": entry_id, "title": entry.title}),
        stream_id=f"knowledge:{entry_id}",
    )


@router.post("/knowledge/search")
async def search_knowledge(
    body: SearchKnowledgeRequest,
    store: InMemoryKnowledgeStore = Depends(knowledge_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if body.query_embedding is not None:
        results = await store.search(
            tuple(body.query_embedding),
            project_id=body.project_id,
            limit=body.limit,
        )
        return [{**_entry_to_dict(entry), "score": round(score, 4)} for entry, score in results]
    # Fallback: simple substring match on title and content
    entries = await store.list_all(project_id=body.project_id)
    if body.query:
        q = body.query.lower()
        entries = [e for e in entries if q in e.title.lower() or q in e.content.lower()]
    return [_entry_to_dict(e) for e in entries[: body.limit]]
