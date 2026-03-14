"""In-memory projection engine — subscribes to EventBus for reactive projections."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus, EventStore
    from lintel.domain.projections.protocols import Projection

logger = structlog.get_logger()


class InMemoryProjectionEngine:
    """Dispatches events to registered projections.

    When an EventBus is provided, the engine subscribes to the bus
    and receives events reactively. The ``project()`` method can still
    be called directly for testing or manual replay.
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._projections: list[Projection] = []
        self._event_store = event_store
        self._event_bus = event_bus
        self._subscription_id: str | None = None

    async def register(self, projection: Projection) -> None:
        self._projections.append(projection)
        logger.info(
            "projection_registered",
            event_types=sorted(projection.handled_event_types),
        )

    async def start(self) -> None:
        """Subscribe to the event bus to receive events reactively.

        Call this after all projections have been registered.
        """
        if self._event_bus is None:
            return
        # Collect all handled event types across projections
        all_types: set[str] = set()
        for projection in self._projections:
            all_types.update(projection.handled_event_types)
        self._subscription_id = await self._event_bus.subscribe(
            frozenset(all_types),
            self,
        )
        logger.info(
            "projection_engine_subscribed",
            event_types_count=len(all_types),
            subscription_id=self._subscription_id,
        )

    async def stop(self) -> None:
        """Unsubscribe from the event bus."""
        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None
            logger.info("projection_engine_unsubscribed")

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — called by the EventBus."""
        await self.project(event)

    async def project(self, event: EventEnvelope) -> None:
        for projection in self._projections:
            if event.event_type in projection.handled_event_types:
                await projection.project(event)

    async def reset_all(self) -> None:
        """Reset all projections to empty state."""
        for projection in self._projections:
            await projection.rebuild([])
        logger.info("projections_reset", count=len(self._projections))

    async def rebuild_all(self, stream_id: str) -> None:
        if not self._event_store:
            msg = "EventStore required for rebuild"
            raise RuntimeError(msg)
        events = await self._event_store.read_stream(stream_id)
        for projection in self._projections:
            matching = [e for e in events if e.event_type in projection.handled_event_types]
            await projection.rebuild(matching)
