"""Work queue contracts for REQ-034.1 Concurrency Limiter & Work Queue."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Any
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, Field


class WorkQueueStatus(StrEnum):
    """Status values for a work queue entry."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class WorkQueueEntry(BaseModel, frozen=True):
    """A single entry in the durable work queue."""

    id: UUID
    agent_id: str
    run_id: UUID
    pipeline_id: UUID | None = None
    priority: int = 0
    status: WorkQueueStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentQueuedEvent(BaseModel, frozen=True):
    """Published when an agent run is enqueued."""

    agent_id: str
    run_id: UUID
    queued_at: datetime
    priority: int = 0
