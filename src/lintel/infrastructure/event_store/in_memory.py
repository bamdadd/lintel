"""In-memory event store for development and testing."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus

logger = structlog.get_logger()


class InMemoryEventStore:
    """Implements EventStore protocol with a plain dict.

    Assigns a monotonically increasing ``global_position`` to every appended
    event so that ``read_all`` and ``read_by_event_type`` can use position-based
    filtering (consistent with the Postgres implementation).
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._streams: dict[str, list[EventEnvelope]] = {}
        self._event_bus = event_bus
        self._global_counter: int = 0

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Attach an event bus after construction (for circular-dep wiring)."""
        self._event_bus = event_bus

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None:
        stream = self._streams.setdefault(stream_id, [])
        current_version = len(stream) - 1
        if expected_version is not None and current_version != expected_version:
            msg = f"Expected version {expected_version}, got {current_version}"
            raise ValueError(msg)

        stamped: list[EventEnvelope] = []
        for event in events:
            self._global_counter += 1
            stamped.append(replace(event, global_position=self._global_counter))

        stream.extend(stamped)

        # Publish to event bus after successful persist
        if self._event_bus is not None:
            for event in stamped:
                try:
                    await self._event_bus.publish(event)
                except Exception:
                    logger.warning(
                        "event_bus_publish_failed",
                        event_type=event.event_type,
                        stream_id=stream_id,
                    )

    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[EventEnvelope]:
        stream = self._streams.get(stream_id, [])
        return list(stream[from_version:])

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]:
        all_events: list[EventEnvelope] = []
        for stream in self._streams.values():
            all_events.extend(stream)
        all_events.sort(key=lambda e: (e.global_position or 0))
        filtered = [e for e in all_events if (e.global_position or 0) >= from_position]
        return filtered[:limit]

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]:
        result: list[EventEnvelope] = []
        for stream in self._streams.values():
            for event in stream:
                if event.correlation_id == correlation_id:
                    result.append(event)
        result.sort(key=lambda e: e.occurred_at)
        return result

    async def read_by_event_type(
        self,
        event_type: str,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]:
        all_events: list[EventEnvelope] = []
        for stream in self._streams.values():
            for event in stream:
                if event.event_type == event_type:
                    all_events.append(event)
        all_events.sort(key=lambda e: (e.global_position or 0))
        filtered = [e for e in all_events if (e.global_position or 0) >= from_position]
        return filtered[:limit]

    async def read_by_time_range(
        self,
        from_time: datetime,
        to_time: datetime,
        event_types: frozenset[str] | None = None,
    ) -> list[EventEnvelope]:
        result: list[EventEnvelope] = []
        for stream in self._streams.values():
            for event in stream:
                if from_time <= event.occurred_at <= to_time and (
                    event_types is None or event.event_type in event_types
                ):
                    result.append(event)
        result.sort(key=lambda e: e.occurred_at)
        return result
