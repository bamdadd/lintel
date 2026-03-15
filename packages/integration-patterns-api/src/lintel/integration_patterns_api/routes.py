"""Integration pattern endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.contracts.events import EventEnvelope
from lintel.integration_patterns_api.events import (
    INTEGRATION_MAP_CREATED,
)
from lintel.integration_patterns_api.types import IntegrationMap

if TYPE_CHECKING:
    from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore

router = APIRouter()

integration_pattern_store_provider: StoreProvider[InMemoryIntegrationPatternStore] = StoreProvider()


# --- Request models ---


class CreateIntegrationMapRequest(BaseModel):
    repository_id: str
    workflow_run_id: str = ""


# --- Helpers ---


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# --- Integration map endpoints ---


@router.post("/integration-maps", status_code=201)
async def create_integration_map(
    body: CreateIntegrationMapRequest,
    request: Request,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> dict[str, Any]:
    now = _now_iso()
    map_id = str(uuid4())
    integration_map = IntegrationMap(
        map_id=map_id,
        repository_id=body.repository_id,
        workflow_run_id=body.workflow_run_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    await store.create_map(integration_map)
    await dispatch_event(
        request,
        EventEnvelope(
            event_type=INTEGRATION_MAP_CREATED,
            payload={
                "resource_id": map_id,
                "repository_id": body.repository_id,
            },
        ),
        stream_id=f"integration_map:{map_id}",
    )
    return asdict(integration_map)


@router.get("/integration-maps")
async def list_integration_maps(
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
    repository_id: str | None = None,
) -> list[dict[str, Any]]:
    maps = await store.list_maps(repository_id=repository_id)
    return [asdict(m) for m in maps]


@router.get("/integration-maps/{map_id}")
async def get_integration_map(
    map_id: str,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> dict[str, Any]:
    integration_map = await store.get_map(map_id)
    if integration_map is None:
        raise HTTPException(status_code=404, detail="Integration map not found")
    return asdict(integration_map)


@router.get("/integration-maps/{map_id}/graph")
async def get_integration_graph(
    map_id: str,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> dict[str, Any]:
    integration_map = await store.get_map(map_id)
    if integration_map is None:
        raise HTTPException(status_code=404, detail="Integration map not found")
    nodes = await store.get_nodes(map_id)
    edges = await store.get_edges(map_id)
    return {
        "map_id": map_id,
        "nodes": [asdict(n) for n in nodes],
        "edges": [asdict(e) for e in edges],
    }


@router.get("/integration-maps/{map_id}/patterns")
async def get_patterns(
    map_id: str,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> list[dict[str, Any]]:
    integration_map = await store.get_map(map_id)
    if integration_map is None:
        raise HTTPException(status_code=404, detail="Integration map not found")
    patterns = await store.get_patterns(map_id)
    return [asdict(p) for p in patterns]


@router.get("/integration-maps/{map_id}/antipatterns")
async def get_antipatterns(
    map_id: str,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> list[dict[str, Any]]:
    integration_map = await store.get_map(map_id)
    if integration_map is None:
        raise HTTPException(status_code=404, detail="Integration map not found")
    detections = await store.get_antipatterns(map_id)
    return [asdict(d) for d in detections]


@router.get("/integration-maps/{map_id}/coupling-scores")
async def get_coupling_scores(
    map_id: str,
    store: InMemoryIntegrationPatternStore = Depends(  # noqa: B008
        integration_pattern_store_provider
    ),
) -> list[dict[str, Any]]:
    integration_map = await store.get_map(map_id)
    if integration_map is None:
        raise HTTPException(status_code=404, detail="Integration map not found")
    scores = await store.get_coupling_scores(map_id)
    return [asdict(s) for s in scores]
