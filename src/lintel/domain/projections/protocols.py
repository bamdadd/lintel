"""Projection protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class Projection(Protocol):
    """A projection that builds a read model from events."""

    @property
    def handled_event_types(self) -> set[str]: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild(self, events: list[EventEnvelope]) -> None: ...


class ProjectionEngine(Protocol):
    """Dispatches events to registered projections."""

    async def register(self, projection: Projection) -> None: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild_all(self, stream_id: str) -> None: ...
