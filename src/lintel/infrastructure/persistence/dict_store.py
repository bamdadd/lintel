"""Postgres-backed store for dict-based entities (ChatStore, AgentDefinitionStore, etc.)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


class PostgresDictStore:
    """Generic CRUD store for entities stored as plain dicts (not dataclasses)."""

    def __init__(self, pool: asyncpg.Pool, kind: str) -> None:
        self._pool = pool
        self._kind = kind

    async def put(self, entity_id: str, data: dict[str, Any]) -> None:
        """Insert or update an entity."""
        async with self._pool.acquire() as conn:
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
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            if row is None:
                return None
            return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]

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
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows
            ]

    async def remove(self, entity_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            return result == "DELETE 1"
