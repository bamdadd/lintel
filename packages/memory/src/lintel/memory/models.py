"""Domain models for the memory subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Classification of a stored memory."""

    LONG_TERM = "long_term"
    EPISODIC = "episodic"


class MemoryFact(BaseModel):
    """A single persisted memory fact."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    memory_type: MemoryType
    fact_type: str
    content: str
    embedding_id: str | None = None
    source_workflow_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryChunk(BaseModel):
    """A memory fact paired with its relevance score and rank."""

    fact: MemoryFact
    score: float
    rank: int


class ScoredPoint(BaseModel):
    """A raw scored result from the vector store."""

    id: str
    score: float
    payload: dict[str, Any]


class MemorySearchResult(BaseModel):
    """Aggregated search results for a memory query."""

    query: str
    chunks: list[MemoryChunk]
    total: int
