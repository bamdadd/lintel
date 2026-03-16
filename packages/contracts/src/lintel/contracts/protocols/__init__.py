"""Protocol interfaces defining service boundaries.

Domain code depends on these abstractions. Infrastructure provides implementations.
No concrete imports from infrastructure in this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from lintel.contracts.protocols.artifact_store import ArtifactRef, ArtifactStore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope

__all__ = [
    "ArtifactRef",
    "ArtifactStore",
    "CommandDispatcher",
    "EventBus",
    "EventHandler",
    "EventStore",
]


class EventHandler(Protocol):
    """Handles a single event delivered by the EventBus."""

    async def handle(self, event: EventEnvelope) -> None: ...


class EventBus(Protocol):
    """Publish-subscribe bus for domain events."""

    async def publish(self, event: EventEnvelope) -> None: ...

    async def subscribe(
        self,
        event_types: frozenset[str],
        handler: EventHandler,
    ) -> str: ...

    async def unsubscribe(self, subscription_id: str) -> None: ...


class CommandDispatcher(Protocol):
    """Routes commands to registered handlers."""

    async def dispatch(self, command: object) -> object: ...


class EventStore(Protocol):
    """Append-only event persistence with optimistic concurrency."""

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None: ...

    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[EventEnvelope]: ...

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]: ...

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]: ...

    async def read_by_event_type(
        self,
        event_type: str,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]: ...

    async def read_by_time_range(
        self,
        from_time: datetime,
        to_time: datetime,
        event_types: frozenset[str] | None = None,
    ) -> list[EventEnvelope]: ...
