"""Thread query endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from lintel.api.deps import get_thread_status_projection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection

router = APIRouter()


@router.get("/threads")
async def list_threads(
    projection: Annotated[ThreadStatusProjection, Depends(get_thread_status_projection)],
) -> list[dict[str, Any]]:
    """List all thread statuses."""
    return projection.get_all()
