"""Postgres-backed store for dict-based entities (ChatStore, AgentDefinitionStore, etc.)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


class PostgresComplianceStore:
    """Postgres-backed store matching the ComplianceStore interface for compliance entities."""

    def __init__(self, pool: asyncpg.Pool, kind: str, id_field: str) -> None:
        self._store = PostgresDictStore(pool, kind)
        self._id_field = id_field

    def _to_dict(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        from dataclasses import asdict, fields

        if hasattr(entity, "__dataclass_fields__"):
            data = asdict(entity)
            for k, v in data.items():
                if isinstance(v, (tuple, frozenset)):
                    data[k] = list(v)
            return data
        return dict(entity) if not isinstance(entity, dict) else entity

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        entity_id = data[self._id_field]
        await self._store.put(entity_id, data)
        return data

    async def get(self, entity_id: str) -> dict[str, Any] | None:
        return await self._store.get(entity_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._store.list_all()

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return await self._store.list_all(project_id=project_id)

    async def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self._store.get(entity_id)
        if existing is None:
            return None
        merged = {**existing, **data}
        await self._store.put(entity_id, merged)
        return merged

    async def remove(self, entity_id: str) -> bool:
        return await self._store.remove(entity_id)


class PostgresDictStore:
    """Generic CRUD store for entities stored as plain dicts (not dataclasses)."""

    def __init__(self, pool: asyncpg.Pool, kind: str) -> None:
        self._pool = pool
        self._kind = kind

    async def put(self, entity_id: str, data: dict[str, Any]) -> None:
        """Insert or update an entity."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                self._kind,
                entity_id,
                json.dumps(data, default=str),
            )

    async def get(self, entity_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            if row is None:
                return None
            return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]  # type: ignore[no-any-return]

    async def list_all(self, **filters: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        conditions = ["kind = $1"]
        params: list[object] = [self._kind]
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

    async def remove(self, entity_id: str) -> bool:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                "DELETE FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            return result == "DELETE 1"  # type: ignore[no-any-return]
