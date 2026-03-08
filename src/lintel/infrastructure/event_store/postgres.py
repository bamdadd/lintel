"""Postgres append-only event store with optimistic concurrency and hash chaining."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from lintel.contracts.events import EVENT_TYPE_MAP, EventEnvelope

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from uuid import UUID

    import asyncpg

    from lintel.contracts.protocols import EventBus

logger = structlog.get_logger()


@runtime_checkable
class RecordLike(Protocol):
    """Minimal interface for asyncpg.Record-like objects."""

    def __getitem__(self, key: str) -> object: ...
    def get(self, key: str, default: object = None) -> object: ...


class PostgresEventStore:
    """Implements EventStore protocol with Postgres backend."""

    def __init__(self, pool: asyncpg.Pool, event_bus: EventBus | None = None) -> None:
        self._pool = pool
        self._event_bus = event_bus

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Attach an event bus after construction (for circular-dep wiring)."""
        self._event_bus = event_bus

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            if expected_version is not None:
                current = await conn.fetchval(
                    "SELECT COALESCE(MAX(stream_version), -1) FROM events WHERE stream_id = $1",
                    stream_id,
                )
                if current != expected_version:
                    raise OptimisticConcurrencyError(
                        f"Expected version {expected_version}, got {current}"
                    )

            prev_hash = await conn.fetchval(
                "SELECT payload_hash FROM events WHERE stream_id = $1 "
                "ORDER BY stream_version DESC LIMIT 1",
                stream_id,
            )

            base_version = (
                expected_version
                if expected_version is not None
                else (
                    await conn.fetchval(
                        "SELECT COALESCE(MAX(stream_version), -1) FROM events WHERE stream_id = $1",
                        stream_id,
                    )
                )
            )

            # Check idempotency keys before inserting
            for event in events:
                if event.idempotency_key:
                    existing = await conn.fetchval(
                        "SELECT 1 FROM events WHERE idempotency_key = $1",
                        event.idempotency_key,
                    )
                    if existing:
                        raise IdempotencyViolationError(
                            f"Event with idempotency_key={event.idempotency_key} already exists"
                        )

            for i, event in enumerate(events):
                version = base_version + 1 + i
                payload_json = json.dumps(event.payload, sort_keys=True, default=str)
                payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

                thread_ref_json = None
                if event.thread_ref:
                    thread_ref_json = json.dumps(
                        {
                            "workspace_id": event.thread_ref.workspace_id,
                            "channel_id": event.thread_ref.channel_id,
                            "thread_ts": event.thread_ref.thread_ts,
                        }
                    )

                await conn.execute(
                    """
                    INSERT INTO events (
                        event_id, stream_id, stream_version, event_type,
                        schema_version, occurred_at, actor_type, actor_id,
                        correlation_id, causation_id, thread_ref,
                        payload, payload_hash, prev_hash, idempotency_key
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                        $12::jsonb,$13,$14,$15
                    )
                    """,
                    event.event_id,
                    stream_id,
                    version,
                    event.event_type,
                    event.schema_version,
                    event.occurred_at,
                    event.actor_type.value,
                    event.actor_id,
                    event.correlation_id,
                    event.causation_id,
                    thread_ref_json,
                    payload_json,
                    payload_hash,
                    prev_hash,
                    event.idempotency_key,
                )
                prev_hash = payload_hash

            logger.info(
                "events_appended",
                stream_id=stream_id,
                count=len(events),
                new_version=base_version + len(events),
            )

        # Publish to event bus after successful persist (outside transaction)
        if self._event_bus is not None:
            for event in events:
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
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events "
                "WHERE stream_id = $1 AND stream_version >= $2 "
                "ORDER BY stream_version",
                stream_id,
                from_version,
            )
            return [_row_to_event(row) for row in rows]

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events ORDER BY occurred_at, stream_version OFFSET $1 LIMIT $2",
                from_position,
                limit,
            )
            return [_row_to_event(row) for row in rows]

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE correlation_id = $1 ORDER BY occurred_at",
                correlation_id,
            )
            return [_row_to_event(row) for row in rows]

    async def read_by_event_type(
        self,
        event_type: str,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE event_type = $1 "
                "ORDER BY occurred_at OFFSET $2 LIMIT $3",
                event_type,
                from_position,
                limit,
            )
            return [_row_to_event(row) for row in rows]

    async def read_by_time_range(
        self,
        from_time: datetime,
        to_time: datetime,
        event_types: frozenset[str] | None = None,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            if event_types:
                rows = await conn.fetch(
                    "SELECT * FROM events "
                    "WHERE occurred_at >= $1 AND occurred_at <= $2 "
                    "AND event_type = ANY($3::text[]) "
                    "ORDER BY occurred_at",
                    from_time,
                    to_time,
                    list(event_types),
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM events "
                    "WHERE occurred_at >= $1 AND occurred_at <= $2 "
                    "ORDER BY occurred_at",
                    from_time,
                    to_time,
                )
            return [_row_to_event(row) for row in rows]


class OptimisticConcurrencyError(Exception):
    pass


class IdempotencyViolationError(Exception):
    pass


def _row_to_event(row: Mapping[str, object] | RecordLike) -> EventEnvelope:
    """Deserialize a database row to an EventEnvelope."""
    from lintel.contracts.types import ActorType, ThreadRef

    thread_ref = None
    raw_thread_ref = row["thread_ref"]
    if raw_thread_ref:
        tr = json.loads(raw_thread_ref) if isinstance(raw_thread_ref, str) else raw_thread_ref
        thread_ref = ThreadRef(
            workspace_id=tr["workspace_id"],  # type: ignore[index]
            channel_id=tr["channel_id"],  # type: ignore[index]
            thread_ts=tr["thread_ts"],  # type: ignore[index]
        )

    raw_payload = row["payload"]
    payload: dict[str, object] = (
        json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload  # type: ignore[assignment]
    )

    cls = EVENT_TYPE_MAP.get(str(row["event_type"]), EventEnvelope)
    return cls(
        event_id=row["event_id"],  # type: ignore[arg-type]
        event_type=str(row["event_type"]),
        schema_version=row["schema_version"],  # type: ignore[arg-type]
        occurred_at=row["occurred_at"],  # type: ignore[arg-type]
        actor_type=ActorType(str(row["actor_type"])),
        actor_id=str(row["actor_id"]),
        thread_ref=thread_ref,
        correlation_id=row["correlation_id"],  # type: ignore[arg-type]
        causation_id=row["causation_id"],  # type: ignore[arg-type]
        payload=payload,
        idempotency_key=row.get("idempotency_key"),  # type: ignore[arg-type]
    )
