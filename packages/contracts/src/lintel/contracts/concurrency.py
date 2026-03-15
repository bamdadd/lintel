"""Concurrency limiter contracts for REQ-034.1."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel


class ConcurrencyState(BaseModel, frozen=True):
    """Snapshot of the concurrency limiter state."""

    active_slots: int
    max_slots: int
    queue_depth: int


class SlotAcquiredEvent(BaseModel, frozen=True):
    """Published when an agent acquires a concurrency slot."""

    agent_id: str
    run_id: UUID
    acquired_at: datetime


class SlotReleasedEvent(BaseModel, frozen=True):
    """Published when an agent releases a concurrency slot."""

    agent_id: str
    run_id: UUID
    released_at: datetime
    outcome: str
