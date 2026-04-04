"""In-memory knowledge graph store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.knowledge_graph_api.types import (
        Flow,
        GraphEdge,
        GraphNode,
        KnowledgeGraph,
        ScanResult,
        Schema,
    )


class InMemoryKnowledgeGraphStore:
    """Simple in-memory store for the knowledge graph."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._flows: dict[str, Flow] = {}
        self._schemas: dict[str, Schema] = {}
        self._scans: dict[str, ScanResult] = {}

    # --- Scan operations ---

    async def add_scan(self, scan: ScanResult) -> None:
        self._scans[scan.id] = scan

    async def get_scan(self, scan_id: str) -> ScanResult | None:
        return self._scans.get(scan_id)

    async def update_scan(self, scan: ScanResult) -> None:
        self._scans[scan.id] = scan

    # --- Node operations ---

    async def add_node(self, node: GraphNode) -> None:
        self._nodes[node.id] = node

    async def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    async def list_nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    # --- Edge operations ---

    async def add_edge(self, edge: GraphEdge) -> None:
        self._edges.append(edge)

    async def list_edges(self) -> list[GraphEdge]:
        return list(self._edges)

    # --- Flow operations ---

    async def add_flow(self, flow: Flow) -> None:
        self._flows[flow.id] = flow

    async def list_flows(self) -> list[Flow]:
        return list(self._flows.values())

    # --- Schema operations ---

    async def add_schema(self, schema: Schema) -> None:
        self._schemas[schema.id] = schema

    async def list_schemas(self) -> list[Schema]:
        return list(self._schemas.values())

    # --- Graph retrieval ---

    async def get_graph(self) -> KnowledgeGraph:
        from lintel.knowledge_graph_api.types import KnowledgeGraph

        return KnowledgeGraph(
            nodes=tuple(self._nodes.values()),
            edges=tuple(self._edges),
            flows=tuple(self._flows.values()),
            schemas=tuple(self._schemas.values()),
        )

    async def clear(self) -> None:
        """Clear all graph data."""
        self._nodes.clear()
        self._edges.clear()
        self._flows.clear()
        self._schemas.clear()
