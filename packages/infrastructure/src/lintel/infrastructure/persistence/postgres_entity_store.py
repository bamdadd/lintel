"""Generic Postgres-backed entity store using JSONB."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


class PostgresEntityStore:
    """Generic CRUD store backed by the ``entities`` table.

    Each instance is scoped to a *kind* (e.g. ``"repository"``, ``"team"``).
    Entities are stored as JSONB in the ``data`` column and keyed by
    ``(kind, entity_id)``.
    """

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
        """Get a single entity by ID."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            if row is None:
                return None
            return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]  # type: ignore[no-any-return]

    async def list_all(self) -> list[dict[str, Any]]:
        """List all entities of this kind."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(
                "SELECT data FROM entities WHERE kind = $1 ORDER BY created_at",
                self._kind,
            )
            return [
                json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows
            ]

    async def remove(self, entity_id: str) -> bool:
        """Delete an entity. Returns True if it existed."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                "DELETE FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                entity_id,
            )
            return result == "DELETE 1"  # type: ignore[no-any-return]

    async def find(self, **filters: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        """Find entities matching JSONB field filters.

        Example: ``store.find(project_id="p1")`` finds entities where
        ``data->>'project_id' = 'p1'``.
        """
        conditions = ["kind = $1"]
        params: list[object] = [self._kind]
        for i, (key, value) in enumerate(filters.items(), start=2):
            if value is not None:
                conditions.append(f"data->>'{key}' = ${i}")
                params.append(str(value))

        query = f"SELECT data FROM entities WHERE {' AND '.join(conditions)} ORDER BY created_at"
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(query, *params)
            return [
                json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in rows
            ]
