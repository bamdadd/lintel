"""In-memory event store for development and testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from lintel.contracts.events import EventEnvelope


class InMemoryEventStore:
    """Implements EventStore protocol with a plain dict."""

    def __init__(self) -> None:
        self._streams: dict[str, list[EventEnvelope]] = {}

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
        stream.extend(events)

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
        all_events.sort(key=lambda e: e.occurred_at)
        return all_events[from_position : from_position + limit]

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
