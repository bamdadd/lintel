"""Event envelope base class and registry.

This module provides the kernel for Lintel's event-sourced architecture:
- EventEnvelope: base class for all domain events
- EVENT_TYPE_MAP / register_events / deserialize_event: global event registry

Concrete event classes live in their respective domain packages
(lintel.domain.events, lintel.workflows.events, lintel.agents.events, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from lintel.contracts.types import ActorType, ThreadRef


@dataclass(frozen=True)
class EventEnvelope:
    """Shared envelope for all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    schema_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = ""
    thread_ref: ThreadRef | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    global_position: int | None = None


# --- Event Registry ---

EVENT_TYPE_MAP: dict[str, type[EventEnvelope]] = {}


def register_events(*classes: type[EventEnvelope]) -> None:
    """Register event classes into the global EVENT_TYPE_MAP."""
    for cls in classes:
        EVENT_TYPE_MAP[cls.event_type] = cls


def deserialize_event(event_type: str, data: dict[str, Any]) -> EventEnvelope:
    """Deserialize an event from stored data. Raises KeyError for unknown types."""
    cls = EVENT_TYPE_MAP[event_type]
    return cls(**data)
