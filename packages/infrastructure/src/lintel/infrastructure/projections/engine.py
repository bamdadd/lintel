"""In-memory projection engine — subscribes to EventBus for reactive projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus, EventStore
    from lintel.domain.projections.protocols import Projection, ProjectionStore

from lintel.contracts.projections import ProjectionState, ProjectionStatus

logger = structlog.get_logger()


@dataclass
class _ProjectionMeta:
    """Internal tracking state per registered projection."""

    projection: Any  # Projection protocol
    global_position: int = 0
    events_processed: int = 0
    last_event_at: datetime | None = None


class InMemoryProjectionEngine:
    """Dispatches events to registered projections.

    When an EventBus is provided, the engine subscribes to the bus
    and receives events reactively. The ``project()`` method can still
    be called directly for testing or manual replay.

    When a ProjectionStore is provided, the engine persists projection
    state periodically (every ``snapshot_interval`` events) and restores
    state on ``start()``.
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
        projection_store: ProjectionStore | None = None,
        snapshot_interval: int = 100,
    ) -> None:
        self._metas: list[_ProjectionMeta] = []
        self._event_store = event_store
        self._event_bus = event_bus
        self._projection_store = projection_store
        self._snapshot_interval = snapshot_interval
        self._subscription_id: str | None = None
        self._running = False

    @property
    def _projections(self) -> list[Any]:
        """Backward compat for code accessing _projections directly."""
        return [m.projection for m in self._metas]

    async def register(self, projection: Projection) -> None:
        self._metas.append(_ProjectionMeta(projection=projection))
        logger.info(
            "projection_registered",
            name=projection.name,
            event_types=sorted(projection.handled_event_types),
        )

    async def start(self) -> None:
        """Restore state from store, then subscribe to the event bus."""
        # Restore persisted state
        if self._projection_store is not None:
            for meta in self._metas:
                saved = await self._projection_store.load(meta.projection.name)
                if saved is not None:
                    meta.projection.restore_state(saved.state)
                    meta.global_position = saved.global_position
                    logger.info(
                        "projection_state_restored",
                        name=meta.projection.name,
                        position=saved.global_position,
                    )

        # Subscribe to event bus
        if self._event_bus is not None:
            all_types: set[str] = set()
            for meta in self._metas:
                all_types.update(meta.projection.handled_event_types)
            self._subscription_id = await self._event_bus.subscribe(
                frozenset(all_types),
                self,
            )
            logger.info(
                "projection_engine_subscribed",
                event_types_count=len(all_types),
                subscription_id=self._subscription_id,
            )

        self._running = True

    async def stop(self) -> None:
        """Flush state to store and unsubscribe from the event bus."""
        if self._projection_store is not None:
            for meta in self._metas:
                await self._persist(meta)

        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

        self._running = False
        logger.info("projection_engine_stopped")

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — called by the EventBus."""
        await self.project(event)

    async def project(self, event: EventEnvelope) -> None:
        for meta in self._metas:
            if event.event_type in meta.projection.handled_event_types:
                await meta.projection.project(event)
                meta.events_processed += 1
                if event.global_position is not None:
                    meta.global_position = event.global_position
                meta.last_event_at = event.occurred_at

                # Periodic persistence
                if (
                    self._projection_store is not None
                    and meta.events_processed % self._snapshot_interval == 0
                ):
                    await self._persist(meta)

    async def _persist(self, meta: _ProjectionMeta) -> None:
        """Save projection state to the store."""
        if self._projection_store is None:
            return
        state = ProjectionState(
            projection_name=meta.projection.name,
            global_position=meta.global_position,
            stream_position=None,
            state=meta.projection.get_state(),
            updated_at=datetime.now(UTC),
        )
        await self._projection_store.save(state)
        logger.debug(
            "projection_state_persisted",
            name=meta.projection.name,
            position=meta.global_position,
        )

    async def reset_all(self) -> None:
        """Reset all projections to empty state and clear persisted state."""
        for meta in self._metas:
            await meta.projection.rebuild([])
            meta.global_position = 0
            meta.events_processed = 0
            meta.last_event_at = None
            if self._projection_store is not None:
                await self._projection_store.delete(meta.projection.name)
        logger.info("projections_reset", count=len(self._metas))

    async def rebuild_all(self, stream_id: str) -> None:
        if not self._event_store:
            msg = "EventStore required for rebuild"
            raise RuntimeError(msg)
        events = await self._event_store.read_stream(stream_id)
        for meta in self._metas:
            matching = [
                e for e in events if e.event_type in meta.projection.handled_event_types
            ]
            await meta.projection.rebuild(matching)
            if matching:
                last = matching[-1]
                if last.global_position is not None:
                    meta.global_position = last.global_position
                meta.events_processed = len(matching)

    async def get_status(self) -> list[ProjectionStatus]:
        """Return runtime status for all registered projections."""
        statuses: list[ProjectionStatus] = []
        for meta in self._metas:
            statuses.append(
                ProjectionStatus(
                    name=meta.projection.name,
                    status="running" if self._running else "stopped",
                    global_position=meta.global_position,
                    lag=0,
                    last_event_at=meta.last_event_at,
                    events_processed=meta.events_processed,
                )
            )
        return statuses
