"""In-memory knowledge edge store with graph traversal."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


class KnowledgeEdgeStore:
    """In-memory store for knowledge edges with DAG traversal."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _to_dict(entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entity)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        return data

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        edge_id = data["edge_id"]
        # Enforce uniqueness on (from_id, to_id, edge_type)
        for existing in self._data.values():
            if (
                existing["from_id"] == data["from_id"]
                and existing["to_id"] == data["to_id"]
                and existing["edge_type"] == data["edge_type"]
            ):
                msg = "Duplicate edge"
                raise ValueError(msg)
        self._data[edge_id] = data
        return data

    async def get(self, edge_id: str) -> dict[str, Any] | None:
        return self._data.get(edge_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def list_by_observation(self, observation_id: str) -> list[dict[str, Any]]:
        return [
            d
            for d in self._data.values()
            if d.get("from_id") == observation_id or d.get("to_id") == observation_id
        ]

    async def traverse(
        self,
        root_id: str,
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """BFS graph traversal with cycle detection, mirroring Postgres recursive CTE."""
        visited: set[str] = {root_id}
        edges: list[dict[str, Any]] = []
        frontier = [root_id]
        depth = 0

        while frontier and depth < max_depth:
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge in self._data.values():
                    if edge["from_id"] == node_id and edge["to_id"] not in visited:
                        visited.add(edge["to_id"])
                        next_frontier.append(edge["to_id"])
                        edges.append(edge)
            frontier = next_frontier
            depth += 1

        return {"node_ids": sorted(visited), "edges": edges}

    async def remove(self, edge_id: str) -> bool:
        return self._data.pop(edge_id, None) is not None
