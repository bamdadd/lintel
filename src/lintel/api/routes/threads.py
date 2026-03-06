"""Thread and event query endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lintel.api.deps import get_task_backlog_projection, get_thread_status_projection
from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection

router = APIRouter()


@router.get("/threads")
async def list_threads(
    projection: Annotated[ThreadStatusProjection, Depends(get_thread_status_projection)],
) -> list[dict[str, Any]]:
    """List all thread statuses."""
    return projection.get_all()


@router.get("/events")
async def list_events(
    projection: Annotated[TaskBacklogProjection, Depends(get_task_backlog_projection)],
) -> list[dict[str, Any]]:
    """List task backlog events."""
    return projection.get_backlog()
