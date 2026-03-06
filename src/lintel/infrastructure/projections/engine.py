"""In-memory projection engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventStore
    from lintel.domain.projections.protocols import Projection

logger = structlog.get_logger()


class InMemoryProjectionEngine:
    """Dispatches events to registered projections."""

    def __init__(self, event_store: EventStore | None = None) -> None:
        self._projections: list[Projection] = []
        self._event_store = event_store

    async def register(self, projection: Projection) -> None:
        self._projections.append(projection)
        logger.info(
            "projection_registered",
            event_types=sorted(projection.handled_event_types),
        )

    async def project(self, event: EventEnvelope) -> None:
        for projection in self._projections:
            if event.event_type in projection.handled_event_types:
                await projection.project(event)

    async def rebuild_all(self, stream_id: str) -> None:
        if not self._event_store:
            msg = "EventStore required for rebuild"
            raise RuntimeError(msg)
        events = await self._event_store.read_stream(stream_id)
        for projection in self._projections:
            matching = [e for e in events if e.event_type in projection.handled_event_types]
            await projection.rebuild(matching)
