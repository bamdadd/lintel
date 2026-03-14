"""Event store query endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from lintel.api.deps import get_event_store, get_task_backlog_projection
from lintel.contracts.events import EVENT_TYPE_MAP, EventEnvelope
from lintel.contracts.protocols import EventStore
from lintel.projections.task_backlog import TaskBacklogProjection

router = APIRouter()


def _envelope_to_dict(e: EventEnvelope) -> dict[str, Any]:
    return {
        "event_id": str(e.event_id),
        "event_type": e.event_type,
        "payload": e.payload,
        "occurred_at": (
            e.occurred_at.isoformat() if hasattr(e.occurred_at, "isoformat") else str(e.occurred_at)
        ),
        "actor_id": e.actor_id,
        "actor_type": (e.actor_type.value if hasattr(e.actor_type, "value") else str(e.actor_type)),
        "correlation_id": str(e.correlation_id) if e.correlation_id else None,
    }


class PaginatedEventsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


@router.get("/events/types")
async def list_event_types() -> list[str]:
    """List all registered event types (useful for filter dropdowns)."""
    return sorted(EVENT_TYPE_MAP.keys())


@router.get("/events")
async def list_events(
    projection: Annotated[TaskBacklogProjection, Depends(get_task_backlog_projection)],
) -> list[dict[str, Any]]:
    """List all events from the task backlog projection."""
    return projection.get_backlog()


@router.get("/events/all")
async def list_all_events(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
) -> PaginatedEventsResponse:
    """List all events from the event store with pagination.

    Returns events in reverse chronological order (most recent first).
    Optionally filter by event_type.
    """
    event_store = request.app.state.event_store

    # For Postgres stores, query directly with DESC ordering
    pool = getattr(event_store, "_pool", None)
    if pool is not None:
        async with pool.acquire() as conn:
            if event_type:
                count_row = await conn.fetchrow(
                    "SELECT count(*) FROM events WHERE event_type = $1", event_type
                )
                rows = await conn.fetch(
                    "SELECT * FROM events WHERE event_type = $1 "
                    "ORDER BY occurred_at DESC LIMIT $2 OFFSET $3",
                    event_type,
                    limit,
                    offset,
                )
            else:
                count_row = await conn.fetchrow("SELECT count(*) FROM events")
                rows = await conn.fetch(
                    "SELECT * FROM events ORDER BY occurred_at DESC LIMIT $1 OFFSET $2",
                    limit,
                    offset,
                )
            total = count_row["count"]
            from lintel.event_store.postgres import _row_to_event

            items = [_envelope_to_dict(_row_to_event(r)) for r in rows]
        return PaginatedEventsResponse(items=items, total=total, limit=limit, offset=offset)

    # Fallback for in-memory store
    if event_type:
        all_events = await event_store.read_by_event_type(event_type, from_position=0, limit=10000)
    else:
        all_events = await event_store.read_all(from_position=0, limit=10000)

    all_events.sort(key=lambda e: e.occurred_at, reverse=True)
    total = len(all_events)
    page = all_events[offset : offset + limit]
    return PaginatedEventsResponse(
        items=[_envelope_to_dict(e) for e in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/stream/{stream_id}")
async def get_events_by_stream(
    stream_id: str,
    event_store: Annotated[EventStore, Depends(get_event_store)],
) -> dict[str, Any]:
    """Get events for a specific stream from the event store."""
    envelopes = await event_store.read_stream(stream_id)
    return {"stream_id": stream_id, "events": [_envelope_to_dict(e) for e in envelopes]}


@router.get("/events/correlation/{correlation_id}")
async def get_events_by_correlation(
    correlation_id: str,
    event_store: Annotated[EventStore, Depends(get_event_store)],
) -> dict[str, Any]:
    """Get events by correlation ID from the event store."""
    from uuid import UUID

    try:
        cid = UUID(correlation_id)
    except ValueError:
        return {"correlation_id": correlation_id, "events": []}
    envelopes = await event_store.read_by_correlation(cid)
    return {
        "correlation_id": correlation_id,
        "events": [_envelope_to_dict(e) for e in envelopes],
    }
