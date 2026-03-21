"""Postgres-backed store for process mining entities."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

    from lintel.process_mining_api.types import (
        FlowDiagram,
        FlowEntry,
        FlowMetrics,
        ProcessFlowMap,
    )


class PostgresProcessMiningStore:
    """Postgres-backed store for process flow maps and related entities.

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
            data = row["data"]
            result: dict[str, Any] = json.loads(data) if isinstance(data, str) else data
            return result

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
                json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows
            ]

    # --- Flow maps ---

    async def create_map(self, flow_map: ProcessFlowMap) -> None:
        await self._put("process_flow_map", flow_map.flow_map_id, asdict(flow_map))

    async def get_map(self, flow_map_id: str) -> ProcessFlowMap | None:
        from lintel.process_mining_api.types import ProcessFlowMap

        data = await self._get("process_flow_map", flow_map_id)
        if data is None:
            return None
        return ProcessFlowMap(**data)

    async def list_maps(
        self,
        *,
        repository_id: str | None = None,
    ) -> list[ProcessFlowMap]:
        from lintel.process_mining_api.types import ProcessFlowMap

        rows = await self._list("process_flow_map", repository_id=repository_id)
        return [ProcessFlowMap(**r) for r in rows]

    async def update_map_status(self, flow_map_id: str, status: str) -> None:
        from lintel.process_mining_api.types import ProcessFlowMap

        data = await self._get("process_flow_map", flow_map_id)
        if data is not None:
            existing = ProcessFlowMap(**data)
            updated = replace(existing, status=status)
            await self._put("process_flow_map", flow_map_id, asdict(updated))

    # --- Flow entries ---

    async def add_flows(self, flows: list[FlowEntry]) -> None:
        for flow in flows:
            await self._put("process_flow_entry", flow.flow_id, asdict(flow))

    async def get_flows(
        self,
        flow_map_id: str,
        *,
        flow_type: str | None = None,
    ) -> list[FlowEntry]:
        from lintel.process_mining_api.types import FlowEntry, FlowStep

        filters: dict[str, object] = {"flow_map_id": flow_map_id}
        if flow_type is not None:
            filters["flow_type"] = flow_type
        rows = await self._list("process_flow_entry", **filters)
        results: list[FlowEntry] = []
        for r in rows:
            r["source"] = FlowStep(**r["source"]) if isinstance(r["source"], dict) else r["source"]
            if r.get("sink") and isinstance(r["sink"], dict):
                r["sink"] = FlowStep(**r["sink"])
            if "steps" in r and isinstance(r["steps"], list):
                r["steps"] = tuple(FlowStep(**s) if isinstance(s, dict) else s for s in r["steps"])
            results.append(FlowEntry(**r))
        return results

    # --- Diagrams ---

    async def add_diagrams(self, diagrams: list[FlowDiagram]) -> None:
        for diagram in diagrams:
            await self._put("process_flow_diagram", diagram.diagram_id, asdict(diagram))

    async def get_diagrams(
        self,
        flow_map_id: str,
        *,
        flow_type: str | None = None,
    ) -> list[FlowDiagram]:
        from lintel.process_mining_api.types import FlowDiagram

        filters: dict[str, object] = {"flow_map_id": flow_map_id}
        if flow_type is not None:
            filters["flow_type"] = flow_type
        rows = await self._list("process_flow_diagram", **filters)
        results: list[FlowDiagram] = []
        for r in rows:
            if "flow_ids" in r and isinstance(r["flow_ids"], list):
                r["flow_ids"] = tuple(r["flow_ids"])
            results.append(FlowDiagram(**r))
        return results

    # --- Metrics ---

    async def set_metrics(self, metrics: FlowMetrics) -> None:
        await self._put("process_flow_metrics", metrics.metrics_id, asdict(metrics))

    async def get_metrics(self, flow_map_id: str) -> FlowMetrics | None:
        from lintel.process_mining_api.types import FlowMetrics

        rows = await self._list("process_flow_metrics", flow_map_id=flow_map_id)
        if not rows:
            return None
        return FlowMetrics(**rows[0])
