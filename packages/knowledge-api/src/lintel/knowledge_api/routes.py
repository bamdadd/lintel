"""Knowledge graph REST API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import KnowledgeEdgeCreated
from lintel.domain.types import KnowledgeEdge

if TYPE_CHECKING:
    from lintel.knowledge_api.store import KnowledgeEdgeStore

router = APIRouter()

knowledge_edge_store_provider: StoreProvider[KnowledgeEdgeStore] = StoreProvider()


class CreateKnowledgeEdgeRequest(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid4()))
    from_id: str
    to_id: str
    edge_type: str = "inspired_by"
    created_at: str = ""


@router.post("/knowledge/edges", status_code=201)
async def create_edge(
    request: Request,
    body: CreateKnowledgeEdgeRequest,
    store: KnowledgeEdgeStore = Depends(knowledge_edge_store_provider),  # noqa: B008
) -> dict[str, Any]:
    edge = KnowledgeEdge(
        edge_id=body.edge_id,
        from_id=body.from_id,
        to_id=body.to_id,
        edge_type=body.edge_type,
        created_at=body.created_at,
    )
    try:
        result = await store.add(edge)
    except ValueError:
        raise HTTPException(status_code=409, detail="Duplicate edge")  # noqa: B904
    await dispatch_event(
        request,
        KnowledgeEdgeCreated(
            payload={"resource_id": body.edge_id, "from_id": body.from_id, "to_id": body.to_id},
        ),
        stream_id=f"knowledge_edge:{body.edge_id}",
    )
    return result


@router.get("/knowledge/edges/{edge_id}")
async def get_edge(
    edge_id: str,
    store: KnowledgeEdgeStore = Depends(knowledge_edge_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(edge_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    return item


@router.get("/knowledge/graph")
async def get_graph(
    store: KnowledgeEdgeStore = Depends(knowledge_edge_store_provider),  # noqa: B008
    root_id: str = Query(..., description="Root observation ID for traversal"),
    max_depth: int = Query(5, ge=1, le=20, description="Maximum traversal depth"),
) -> dict[str, Any]:
    return await store.traverse(root_id, max_depth=max_depth)
