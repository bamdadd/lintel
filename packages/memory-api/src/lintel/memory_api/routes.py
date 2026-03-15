"""FastAPI router for the memory subsystem."""

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from lintel.memory_api.dependencies import memory_service_provider
from lintel.memory_api.schemas import (
    CreateMemoryRequest,
    MemoryChunkResponse,
    MemoryFactResponse,
    MemoryListResponse,
    MemorySearchResponse,
)

if TYPE_CHECKING:
    from lintel.memory.memory_service import MemoryService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["memory"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_service() -> "MemoryService":
    return memory_service_provider()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/memory", response_model=MemoryListResponse)
async def list_memories(
    project_id: UUID = Query(...),  # noqa: B008
    memory_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: "MemoryService" = Depends(_get_service),  # noqa: B008
) -> MemoryListResponse:
    """List memory facts with pagination."""
    items, total = await service.list_memories(
        project_id=project_id,
        memory_type=memory_type,
        page=page,
        page_size=page_size,
    )
    return MemoryListResponse(
        items=[MemoryFactResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/memory/search", response_model=MemorySearchResponse)
async def search_memories(
    q: str = Query(...),
    project_id: UUID = Query(...),  # noqa: B008
    memory_type: str | None = Query(None),
    top_k: int = Query(5, ge=1, le=100),
    service: "MemoryService" = Depends(_get_service),  # noqa: B008
) -> MemorySearchResponse:
    """Semantic search over memory facts."""
    chunks = await service.search(
        query=q,
        project_id=project_id,
        memory_type=memory_type,
        top_k=top_k,
    )
    return MemorySearchResponse(
        query=q,
        results=[
            MemoryChunkResponse.model_validate(chunk, from_attributes=True) for chunk in chunks
        ],
        total=len(chunks),
    )


@router.get("/memory/{memory_id}", response_model=MemoryFactResponse)
async def get_memory(
    memory_id: UUID,
    service: "MemoryService" = Depends(_get_service),  # noqa: B008
) -> MemoryFactResponse:
    """Retrieve a single memory fact by ID."""
    fact = await service.get_memory(memory_id=memory_id)
    if fact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    return MemoryFactResponse.model_validate(fact, from_attributes=True)


@router.post(
    "/memory",
    response_model=MemoryFactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(
    body: CreateMemoryRequest,
    service: "MemoryService" = Depends(_get_service),  # noqa: B008
) -> MemoryFactResponse:
    """Create a new memory fact."""
    fact = await service.create_memory(
        project_id=body.project_id,
        content=body.content,
        memory_type=body.memory_type,
        fact_type=body.fact_type,
        source_workflow_id=body.source_workflow_id,
    )
    return MemoryFactResponse.model_validate(fact, from_attributes=True)


@router.delete(
    "/memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory(
    memory_id: UUID,
    service: "MemoryService" = Depends(_get_service),  # noqa: B008
) -> None:
    """Delete a memory fact."""
    deleted = await service.delete_memory(memory_id=memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
