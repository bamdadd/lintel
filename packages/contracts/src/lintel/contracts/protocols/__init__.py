"""Protocol interfaces defining service boundaries.

Domain code depends on these abstractions. Infrastructure provides implementations.
No concrete imports from infrastructure in this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from lintel.contracts.protocols.artifact_store import ArtifactRef, ArtifactStore

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
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
    "EventSubscription",
    "SubscriptionHandler",
    "SubscriptionToken",
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

    async def read_all_from_position(
        self,
        position: int = 0,
        batch_size: int = 100,
    ) -> AsyncGenerator[EventEnvelope, None]: ...


type SubscriptionHandler = Callable[[EventEnvelope], Awaitable[None]]
"""Async callback invoked for each event delivered to a subscription."""


class SubscriptionToken(Protocol):
    """Handle returned by a subscription, used to cancel it."""

    async def cancel(self) -> None: ...


class EventSubscription(Protocol):
    """Persistent subscription that delivers events to a handler."""

    async def subscribe(
        self,
        handler: SubscriptionHandler,
        event_types: frozenset[str],
        from_position: int = 0,
    ) -> SubscriptionToken: ...
