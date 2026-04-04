"""Knowledge graph API endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.knowledge_graph_api.store import InMemoryKnowledgeGraphStore

router = APIRouter()

knowledge_graph_store_provider: StoreProvider[InMemoryKnowledgeGraphStore] = StoreProvider()


class ScanRequest(BaseModel):
    """Request to scan repositories for knowledge graph data."""

    repo_ids: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    """Response from a scan request."""

    id: str
    status: str
    repo_ids: list[str]


@router.post("/knowledge-graph/scan", status_code=201)
async def scan_repos(
    body: ScanRequest,
    store: InMemoryKnowledgeGraphStore = Depends(knowledge_graph_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Trigger a scan of repositories to discover integration patterns."""
    from lintel.knowledge_graph_api.types import (
        Flow,
        GraphEdge,
        GraphNode,
        ScanResult,
        Schema,
    )

    scan_id = str(uuid4())
    scan = ScanResult(
        id=scan_id,
        status="running",
        repo_ids=tuple(body.repo_ids),
        started_at=datetime.now(UTC).isoformat(),
    )
    await store.add_scan(scan)

    # Simulate discovery — in a real implementation this would analyse repo contents
    nodes_found = 0
    edges_found = 0
    flows_found = 0
    schemas_found = 0

    for repo_id in body.repo_ids:
        # Create a service node per repo
        node = GraphNode(
            id=f"svc-{repo_id}",
            kind="service",
            name=repo_id,
            repo_id=repo_id,
        )
        await store.add_node(node)
        nodes_found += 1

        # Create a database node per repo
        db_node = GraphNode(
            id=f"db-{repo_id}",
            kind="database",
            name=f"{repo_id}-db",
            repo_id=repo_id,
        )
        await store.add_node(db_node)
        nodes_found += 1

        # Create edge: service -> database
        edge = GraphEdge(
            source_id=f"svc-{repo_id}",
            target_id=f"db-{repo_id}",
            relation="writes",
        )
        await store.add_edge(edge)
        edges_found += 1

        # Create a schema per repo
        schema = Schema(
            id=f"schema-{repo_id}",
            name=f"{repo_id}_schema",
            repo_id=repo_id,
            schema_type="postgres",
        )
        await store.add_schema(schema)
        schemas_found += 1

    # Create cross-repo flows between consecutive repos
    repo_list = body.repo_ids
    for i in range(len(repo_list) - 1):
        flow = Flow(
            id=f"flow-{repo_list[i]}-{repo_list[i + 1]}",
            name=f"{repo_list[i]} -> {repo_list[i + 1]}",
            source_service=repo_list[i],
            target_service=repo_list[i + 1],
            event_type="domain_event",
            transport="kafka",
        )
        await store.add_flow(flow)
        flows_found += 1

    completed_scan = ScanResult(
        id=scan_id,
        status="completed",
        repo_ids=tuple(body.repo_ids),
        nodes_discovered=nodes_found,
        edges_discovered=edges_found,
        flows_discovered=flows_found,
        schemas_discovered=schemas_found,
        started_at=scan.started_at,
        completed_at=datetime.now(UTC).isoformat(),
    )
    await store.update_scan(completed_scan)

    return asdict(completed_scan)


@router.get("/knowledge-graph/scan/{scan_id}")
async def get_scan(
    scan_id: str,
    store: InMemoryKnowledgeGraphStore = Depends(knowledge_graph_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get the status of a scan."""
    scan = await store.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return asdict(scan)


@router.get("/knowledge-graph")
async def get_knowledge_graph(
    store: InMemoryKnowledgeGraphStore = Depends(knowledge_graph_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get the full knowledge graph."""
    graph = await store.get_graph()
    return asdict(graph)


@router.get("/knowledge-graph/flows")
async def list_flows(
    store: InMemoryKnowledgeGraphStore = Depends(knowledge_graph_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all discovered flows."""
    flows = await store.list_flows()
    return [asdict(f) for f in flows]


@router.get("/knowledge-graph/schemas")
async def list_schemas(
    store: InMemoryKnowledgeGraphStore = Depends(knowledge_graph_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all discovered schemas."""
    schemas = await store.list_schemas()
    return [asdict(s) for s in schemas]
