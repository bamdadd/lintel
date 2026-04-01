"""Frozen dataclasses for pipeline DAG visualisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NodeType(StrEnum):
    """Kind of node in a pipeline graph."""

    STAGE = "stage"
    TRIGGER = "trigger"
    ARTIFACT = "artifact"


class EdgeType(StrEnum):
    """Kind of edge connecting two pipeline graph nodes."""

    EXECUTION = "execution"
    DATA_FLOW = "data_flow"
    TRIGGER = "trigger"


@dataclass(frozen=True)
class NodePosition:
    """2-D position hint for layout engines."""

    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class PipelineNode:
    """A single element in the pipeline visualisation graph."""

    node_id: str
    name: str
    node_type: NodeType
    position: NodePosition = field(default_factory=NodePosition)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineEdge:
    """A directed connection between two pipeline graph nodes."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    label: str = ""


@dataclass(frozen=True)
class PipelineGraph:
    """An immutable DAG representing a pipeline run for visualisation."""

    nodes: tuple[PipelineNode, ...] = ()
    edges: tuple[PipelineEdge, ...] = ()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def node_by_id(self, node_id: str) -> PipelineNode | None:
        """Return the node with the given id, or ``None``."""
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def nodes_by_type(self, node_type: NodeType) -> tuple[PipelineNode, ...]:
        """Return all nodes matching *node_type*."""
        return tuple(n for n in self.nodes if n.node_type == node_type)

    def edges_from(self, node_id: str) -> tuple[PipelineEdge, ...]:
        """Return outgoing edges from *node_id*."""
        return tuple(e for e in self.edges if e.source_id == node_id)

    def edges_to(self, node_id: str) -> tuple[PipelineEdge, ...]:
        """Return incoming edges to *node_id*."""
        return tuple(e for e in self.edges if e.target_id == node_id)

    def successors(self, node_id: str) -> tuple[str, ...]:
        """Return ids of nodes directly reachable from *node_id*."""
        return tuple(e.target_id for e in self.edges if e.source_id == node_id)

    def predecessors(self, node_id: str) -> tuple[str, ...]:
        """Return ids of nodes that directly reach *node_id*."""
        return tuple(e.source_id for e in self.edges if e.target_id == node_id)
