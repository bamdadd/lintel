"""Postgres-backed store for integration pattern entities."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

    from lintel.integration_patterns_api.types import (
        AntipatternDetection,
        IntegrationEdge,
        IntegrationMap,
        PatternCatalogueEntry,
        ServiceCouplingScore,
        ServiceNode,
    )


class PostgresIntegrationPatternStore:
    """Postgres-backed store for integration maps and related entities.

    Uses the shared ``entities`` table with different ``kind`` values for each
    sub-entity type.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- helpers ---

    async def _put(self, kind: str, entity_id: str, data: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                kind,
                entity_id,
                json.dumps(data, default=str),
            )

    async def _get(self, kind: str, entity_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                kind,
                entity_id,
            )
            if row is None:
                return None
            return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]

    async def _list(self, kind: str, **filters: object) -> list[dict[str, Any]]:
        conditions = ["kind = $1"]
        params: list[object] = [kind]
        idx = 2
        for key, value in filters.items():
            if value is not None:
                conditions.append(f"data->>'{key}' = ${idx}")
                params.append(str(value))
                idx += 1

        query = f"SELECT data FROM entities WHERE {' AND '.join(conditions)} ORDER BY created_at"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(query, *params)
            return [
                json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                for r in rows
            ]

    # --- Integration maps ---

    async def create_map(self, map: IntegrationMap) -> None:  # noqa: A002
        await self._put("integration_map", map.map_id, asdict(map))

    async def get_map(self, map_id: str) -> IntegrationMap | None:
        from lintel.integration_patterns_api.types import IntegrationMap

        data = await self._get("integration_map", map_id)
        if data is None:
            return None
        return IntegrationMap(**data)

    async def list_maps(
        self,
        *,
        repository_id: str | None = None,
    ) -> list[IntegrationMap]:
        from lintel.integration_patterns_api.types import IntegrationMap

        rows = await self._list("integration_map", repository_id=repository_id)
        return [IntegrationMap(**r) for r in rows]

    async def update_map_status(self, map_id: str, status: str) -> None:
        from lintel.integration_patterns_api.types import IntegrationMap

        data = await self._get("integration_map", map_id)
        if data is not None:
            existing = IntegrationMap(**data)
            updated = replace(existing, status=status)
            await self._put("integration_map", map_id, asdict(updated))

    # --- Service nodes ---

    async def add_nodes(self, nodes: list[ServiceNode]) -> None:
        for node in nodes:
            await self._put("integration_node", node.node_id, asdict(node))

    async def get_nodes(self, integration_map_id: str) -> list[ServiceNode]:
        from lintel.integration_patterns_api.types import ServiceNode

        rows = await self._list("integration_node", integration_map_id=integration_map_id)
        return [ServiceNode(**r) for r in rows]

    # --- Integration edges ---

    async def add_edges(self, edges: list[IntegrationEdge]) -> None:
        for edge in edges:
            await self._put("integration_edge", edge.edge_id, asdict(edge))

    async def get_edges(self, integration_map_id: str) -> list[IntegrationEdge]:
        from lintel.integration_patterns_api.types import IntegrationEdge

        rows = await self._list("integration_edge", integration_map_id=integration_map_id)
        return [IntegrationEdge(**r) for r in rows]

    # --- Pattern catalogue entries ---

    async def add_patterns(self, patterns: list[PatternCatalogueEntry]) -> None:
        for pattern in patterns:
            await self._put("integration_pattern", pattern.entry_id, asdict(pattern))

    async def get_patterns(self, integration_map_id: str) -> list[PatternCatalogueEntry]:
        from lintel.integration_patterns_api.types import PatternCatalogueEntry

        rows = await self._list("integration_pattern", integration_map_id=integration_map_id)
        return [PatternCatalogueEntry(**r) for r in rows]

    # --- Antipattern detections ---

    async def add_antipatterns(self, detections: list[AntipatternDetection]) -> None:
        for detection in detections:
            await self._put("integration_antipattern", detection.detection_id, asdict(detection))

    async def get_antipatterns(self, integration_map_id: str) -> list[AntipatternDetection]:
        from lintel.integration_patterns_api.types import AntipatternDetection

        rows = await self._list("integration_antipattern", integration_map_id=integration_map_id)
        return [AntipatternDetection(**r) for r in rows]

    # --- Service coupling scores ---

    async def add_coupling_scores(self, scores: list[ServiceCouplingScore]) -> None:
        for score in scores:
            await self._put("integration_coupling", score.score_id, asdict(score))

    async def get_coupling_scores(self, integration_map_id: str) -> list[ServiceCouplingScore]:
        from lintel.integration_patterns_api.types import ServiceCouplingScore

        rows = await self._list("integration_coupling", integration_map_id=integration_map_id)
        return [ServiceCouplingScore(**r) for r in rows]
