"""Codebase index CRUD and search endpoints (REQ-026)."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import CodebaseConnected, CodebaseIndexed, CodebaseReindexed
from lintel.domain.types import CodebaseIndex, IndexEntry, IndexStatus

if TYPE_CHECKING:
    from lintel.codebase_index_api.store import InMemoryCodebaseIndexStore

router = APIRouter()

index_store_provider: StoreProvider[InMemoryCodebaseIndexStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dc_to_dict(obj: object) -> dict[str, Any]:
    data = asdict(obj)  # type: ignore[arg-type]
    for k, v in data.items():
        if isinstance(v, tuple | frozenset):
            data[k] = list(v)
    return data


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateIndexRequest(BaseModel):
    index_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    repository_url: str
    branch: str = "main"
    name: str = ""
    description: str = ""
    tags: list[str] = []


class UpdateIndexRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    branch: str | None = None
    status: IndexStatus | None = None
    tags: list[str] | None = None


class CreateEntryRequest(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    file_path: str
    chunk_index: int = 0
    content: str = ""
    language: str = ""
    start_line: int = 0
    end_line: int = 0


class TriggerReindexRequest(BaseModel):
    commit_sha: str = ""


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


# ---------------------------------------------------------------------------
# Index endpoints
# ---------------------------------------------------------------------------


@router.post("/codebase-indices", status_code=201)
async def create_index(
    request: Request,
    body: CreateIndexRequest,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get_index(body.index_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Index already exists")
    index = CodebaseIndex(
        index_id=body.index_id,
        project_id=body.project_id,
        repository_url=body.repository_url,
        branch=body.branch,
        name=body.name,
        description=body.description,
        tags=tuple(body.tags),
    )
    result = await store.add_index(_dc_to_dict(index))
    await dispatch_event(
        request,
        CodebaseConnected(payload={"resource_id": body.index_id}),
        stream_id=f"codebase-index:{body.index_id}",
    )
    return result


@router.get("/codebase-indices")
async def list_indices(
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_indices_by_project(project_id)
    return await store.list_indices()


@router.get("/codebase-indices/{index_id}")
async def get_index(
    index_id: str,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get_index(index_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Index not found")
    return item


@router.patch("/codebase-indices/{index_id}")
async def update_index(
    request: Request,
    index_id: str,
    body: UpdateIndexRequest,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update_index(index_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Index not found")
    await dispatch_event(
        request,
        CodebaseIndexed(payload={"resource_id": index_id}),
        stream_id=f"codebase-index:{index_id}",
    )
    return result


@router.delete("/codebase-indices/{index_id}", status_code=204)
async def remove_index(
    request: Request,
    index_id: str,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> None:
    if not await store.remove_index(index_id):
        raise HTTPException(status_code=404, detail="Index not found")


# ---------------------------------------------------------------------------
# Entry endpoints
# ---------------------------------------------------------------------------


@router.post("/codebase-indices/{index_id}/entries", status_code=201)
async def create_entry(
    index_id: str,
    body: CreateEntryRequest,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> dict[str, Any]:
    if await store.get_index(index_id) is None:
        raise HTTPException(status_code=404, detail="Index not found")
    entry = IndexEntry(
        entry_id=body.entry_id,
        index_id=index_id,
        file_path=body.file_path,
        chunk_index=body.chunk_index,
        content=body.content,
        language=body.language,
        start_line=body.start_line,
        end_line=body.end_line,
    )
    return await store.add_entry(_dc_to_dict(entry))


@router.get("/codebase-indices/{index_id}/entries")
async def list_entries(
    index_id: str,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if await store.get_index(index_id) is None:
        raise HTTPException(status_code=404, detail="Index not found")
    return await store.list_entries_by_index(index_id)


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


@router.get("/codebase-indices/{index_id}/search")
async def search_index(
    index_id: str,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if await store.get_index(index_id) is None:
        raise HTTPException(status_code=404, detail="Index not found")
    return await store.search(index_id, q, limit=limit)


# ---------------------------------------------------------------------------
# Reindex trigger
# ---------------------------------------------------------------------------


@router.post("/codebase-indices/{index_id}/reindex", status_code=202)
async def trigger_reindex(
    request: Request,
    index_id: str,
    body: TriggerReindexRequest,
    store: InMemoryCodebaseIndexStore = Depends(index_store_provider),  # noqa: B008
) -> dict[str, str]:
    existing = await store.get_index(index_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Index not found")
    updates: dict[str, Any] = {"status": IndexStatus.INDEXING.value}
    if body.commit_sha:
        updates["last_commit_sha"] = body.commit_sha
    await store.update_index(index_id, updates)
    await dispatch_event(
        request,
        CodebaseReindexed(payload={"resource_id": index_id}),
        stream_id=f"codebase-index:{index_id}",
    )
    return {"status": "reindex_triggered"}
