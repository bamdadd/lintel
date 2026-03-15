"""Pydantic request/response models for the memory API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateMemoryRequest(BaseModel):
    """Payload for creating a new memory fact."""

    project_id: UUID
    content: str
    memory_type: str
    fact_type: str
    source_workflow_id: UUID | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MemoryFactResponse(BaseModel):
    """Full representation of a persisted memory fact."""

    id: UUID
    project_id: UUID
    memory_type: str
    fact_type: str
    content: str
    embedding_id: str | None
    source_workflow_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MemoryChunkResponse(BaseModel):
    """A scored memory chunk returned from semantic search."""

    id: UUID
    project_id: UUID
    memory_type: str
    fact_type: str
    content: str
    score: float
    rank: int
    source_workflow_id: UUID | None
    created_at: datetime


class MemorySearchResponse(BaseModel):
    """Wrapper for semantic search results."""

    query: str
    results: list[MemoryChunkResponse]
    total: int


class MemoryListResponse(BaseModel):
    """Paginated list of memory facts."""

    items: list[MemoryFactResponse]
    total: int
    page: int
    page_size: int
