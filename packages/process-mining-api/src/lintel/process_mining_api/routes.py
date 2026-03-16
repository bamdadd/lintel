"""Process mining / data flow mapping endpoints."""

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
from lintel.process_mining_api.events import FLOW_MAP_CREATED
from lintel.process_mining_api.types import ProcessFlowMap

if TYPE_CHECKING:
    from lintel.process_mining_api.store import InMemoryProcessMiningStore

router = APIRouter()

process_mining_store_provider: StoreProvider[InMemoryProcessMiningStore] = StoreProvider()


# --- Request models ---


class CreateFlowMapRequest(BaseModel):
    repository_id: str
    workflow_run_id: str = ""


# --- Helpers ---


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# --- Flow map endpoints ---


@router.post("/flow-maps", status_code=201)
async def create_flow_map(
    body: CreateFlowMapRequest,
    request: Request,
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
) -> dict[str, Any]:
    now = _now_iso()
    flow_map_id = str(uuid4())
    flow_map = ProcessFlowMap(
        flow_map_id=flow_map_id,
        repository_id=body.repository_id,
        workflow_run_id=body.workflow_run_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    await store.create_map(flow_map)
    await dispatch_event(
        request,
        EventEnvelope(
            event_type=FLOW_MAP_CREATED,
            payload={
                "resource_id": flow_map_id,
                "repository_id": body.repository_id,
            },
        ),
        stream_id=f"flow_map:{flow_map_id}",
    )
    return asdict(flow_map)


@router.get("/flow-maps")
async def list_flow_maps(
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
    repository_id: str | None = None,
) -> list[dict[str, Any]]:
    maps = await store.list_maps(repository_id=repository_id)
    return [asdict(m) for m in maps]


@router.get("/flow-maps/{flow_map_id}")
async def get_flow_map(
    flow_map_id: str,
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
) -> dict[str, Any]:
    flow_map = await store.get_map(flow_map_id)
    if flow_map is None:
        raise HTTPException(status_code=404, detail="Flow map not found")
    return asdict(flow_map)


@router.get("/flow-maps/{flow_map_id}/flows")
async def get_flows(
    flow_map_id: str,
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
    flow_type: str | None = None,
) -> list[dict[str, Any]]:
    flow_map = await store.get_map(flow_map_id)
    if flow_map is None:
        raise HTTPException(status_code=404, detail="Flow map not found")
    flows = await store.get_flows(flow_map_id, flow_type=flow_type)
    return [asdict(f) for f in flows]


@router.get("/flow-maps/{flow_map_id}/diagrams")
async def get_diagrams(
    flow_map_id: str,
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
    flow_type: str | None = None,
) -> list[dict[str, Any]]:
    flow_map = await store.get_map(flow_map_id)
    if flow_map is None:
        raise HTTPException(status_code=404, detail="Flow map not found")
    diagrams = await store.get_diagrams(flow_map_id, flow_type=flow_type)
    return [asdict(d) for d in diagrams]


@router.get("/flow-maps/{flow_map_id}/metrics")
async def get_metrics(
    flow_map_id: str,
    store: InMemoryProcessMiningStore = Depends(  # noqa: B008
        process_mining_store_provider
    ),
) -> dict[str, Any]:
    flow_map = await store.get_map(flow_map_id)
    if flow_map is None:
        raise HTTPException(status_code=404, detail="Flow map not found")
    metrics = await store.get_metrics(flow_map_id)
    if metrics is None:
        return {"flow_map_id": flow_map_id, "total_flows": 0}
    return asdict(metrics)
