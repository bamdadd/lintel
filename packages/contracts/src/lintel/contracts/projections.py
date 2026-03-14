"""Projection data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class ProjectionState:
    """Persisted state of a projection."""

    projection_name: str
    global_position: int
    stream_position: int | None
    state: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True)
class ProjectionStatus:
    """Runtime status of a projection for health reporting."""

    name: str
    status: str  # "running" | "catching_up" | "stopped" | "error"
    global_position: int
    lag: int
    last_event_at: datetime | None
    events_processed: int
