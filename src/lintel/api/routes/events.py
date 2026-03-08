"""Event store query endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lintel.api.deps import get_event_store, get_task_backlog_projection
from lintel.contracts.events import EVENT_TYPE_MAP
from lintel.infrastructure.event_store.in_memory import InMemoryEventStore
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection

router = APIRouter()


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


@router.get("/events/stream/{stream_id}")
async def get_events_by_stream(
    stream_id: str,
    event_store: Annotated[InMemoryEventStore, Depends(get_event_store)],
) -> dict[str, Any]:
    """Get events for a specific stream from the event store."""
    envelopes = await event_store.read_stream(stream_id)
    events = [
        {
            "event_type": e.event_type,
            "payload": e.payload,
            "occurred_at": (
                e.occurred_at.isoformat()
                if hasattr(e.occurred_at, "isoformat")
                else str(e.occurred_at)
            ),
            "actor_id": e.actor_id,
            "actor_type": (
                e.actor_type.value if hasattr(e.actor_type, "value") else str(e.actor_type)
            ),
        }
        for e in envelopes
    ]
    return {"stream_id": stream_id, "events": events}


@router.get("/events/correlation/{correlation_id}")
async def get_events_by_correlation(
    correlation_id: str,
    event_store: Annotated[InMemoryEventStore, Depends(get_event_store)],
) -> dict[str, Any]:
    """Get events by correlation ID from the event store."""
    from uuid import UUID

    try:
        cid = UUID(correlation_id)
    except ValueError:
        return {"correlation_id": correlation_id, "events": []}
    envelopes = await event_store.read_by_correlation(cid)
    events = [
        {
            "event_type": e.event_type,
            "payload": e.payload,
            "occurred_at": (
                e.occurred_at.isoformat()
                if hasattr(e.occurred_at, "isoformat")
                else str(e.occurred_at)
            ),
            "actor_id": e.actor_id,
        }
        for e in envelopes
    ]
    return {"correlation_id": correlation_id, "events": events}
