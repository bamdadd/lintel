"""Event store query endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lintel.api.deps import get_task_backlog_projection
from lintel.contracts.events import EVENT_TYPE_MAP
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
) -> dict[str, Any]:
    """Get events for a specific stream.

    Placeholder: requires EventStore (PostgreSQL) to be wired.
    """
    return {
        "stream_id": stream_id,
        "events": [],
        "note": "Placeholder — requires EventStore to be wired.",
    }


@router.get("/events/correlation/{correlation_id}")
async def get_events_by_correlation(
    correlation_id: str,
) -> dict[str, Any]:
    """Get events by correlation ID.

    Placeholder: requires EventStore (PostgreSQL) to be wired.
    """
    return {
        "correlation_id": correlation_id,
        "events": [],
        "note": "Placeholder — requires EventStore to be wired.",
    }
