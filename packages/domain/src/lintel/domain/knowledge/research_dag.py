"""Directed acyclic graph of research nodes for cross-run knowledge sharing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lintel.domain.knowledge.models import ResearchEdge, ResearchNode


class CycleError(Exception):
    """Raised when adding an edge would create a cycle."""


class ResearchDAG:
    """Manages a DAG of :class:`ResearchNode` instances linked by :class:`ResearchEdge`."""

    def __init__(self) -> None:
        self._nodes: dict[str, ResearchNode] = {}
        # parent_id -> list of (child_id, edge)
        self._children: dict[str, list[tuple[str, ResearchEdge]]] = {}
        # child_id -> list of (parent_id, edge)
        self._parents: dict[str, list[tuple[str, ResearchEdge]]] = {}

    # -- mutators --

    def add_node(self, node: ResearchNode) -> None:
        """Add a research node. Raises ``ValueError`` if the id already exists."""
        if node.id in self._nodes:
            msg = f"Node {node.id!r} already exists"
            raise ValueError(msg)
        self._nodes[node.id] = node

    def add_edge(self, edge: ResearchEdge) -> None:
        """Add a directed edge. Raises on missing nodes or cycle creation."""
        if edge.parent_id not in self._nodes:
            msg = f"Parent node {edge.parent_id!r} not found"
            raise KeyError(msg)
        if edge.child_id not in self._nodes:
            msg = f"Child node {edge.child_id!r} not found"
            raise KeyError(msg)
        if edge.parent_id == edge.child_id:
            msg = "Self-loops are not allowed"
            raise CycleError(msg)
        # Check whether child is an ancestor of parent (would create cycle)
        if edge.child_id in self.get_ancestors(edge.parent_id):
            msg = f"Adding edge {edge.parent_id!r} -> {edge.child_id!r} would create a cycle"
            raise CycleError(msg)
        self._children.setdefault(edge.parent_id, []).append((edge.child_id, edge))
        self._parents.setdefault(edge.child_id, []).append((edge.parent_id, edge))

    # -- queries --

    def get_node(self, node_id: str) -> ResearchNode:
        """Return a node by id. Raises ``KeyError`` if not found."""
        return self._nodes[node_id]

    @property
    def nodes(self) -> list[ResearchNode]:
        """All nodes in insertion order."""
        return list(self._nodes.values())

    @property
    def edges(self) -> list[ResearchEdge]:
        """All edges."""
        return [edge for pairs in self._children.values() for _, edge in pairs]

    def get_ancestors(self, node_id: str) -> set[str]:
        """Return the set of all ancestor node ids (transitive parents)."""
        visited: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            for parent_id, _ in self._parents.get(current, []):
                if parent_id not in visited:
                    visited.add(parent_id)
                    stack.append(parent_id)
        return visited

    def get_descendants(self, node_id: str) -> set[str]:
        """Return the set of all descendant node ids (transitive children)."""
        visited: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            for child_id, _ in self._children.get(current, []):
                if child_id not in visited:
                    visited.add(child_id)
                    stack.append(child_id)
        return visited

    def find_relevant(self, topic: str) -> list[ResearchNode]:
        """Return nodes whose topic contains *topic* (case-insensitive)."""
        lower = topic.lower()
        return [n for n in self._nodes.values() if lower in n.topic.lower()]

    def merge_findings(self, node_ids: Sequence[str]) -> list[str]:
        """Combine and deduplicate findings from the given node ids."""
        seen: set[str] = set()
        merged: list[str] = []
        for nid in node_ids:
            node = self._nodes[nid]
            for finding in node.findings:
                if finding not in seen:
                    seen.add(finding)
                    merged.append(finding)
        return merged
