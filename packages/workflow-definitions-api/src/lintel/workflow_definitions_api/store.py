"""In-memory and Postgres-backed stores for workflow definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


class InMemoryWorkflowDefinitionStore:
    """In-memory dict-based store for workflow definitions."""

    def __init__(self) -> None:
        self._defs: dict[str, dict[str, Any]] = {}

    async def put(self, definition_id: str, data: dict[str, Any]) -> None:
        self._defs[definition_id] = data

    async def get(self, definition_id: str) -> dict[str, Any] | None:
        return self._defs.get(definition_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._defs.values())

    async def remove(self, definition_id: str) -> bool:
        return self._defs.pop(definition_id, None) is not None


class PostgresWorkflowDefinitionStore:
    """Postgres-backed store for workflow definitions using the entities table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        import json as _json

        self._pool = pool
        self._json = _json
        self._kind = "workflow_definition"

    async def put(self, definition_id: str, data: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (kind, entity_id)
                DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                self._kind,
                definition_id,
                self._json.dumps(data, default=str),
            )

    async def get(self, definition_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                definition_id,
            )
            if row is None:
                return None
            d = row["data"]
            return self._json.loads(d) if isinstance(d, str) else d  # type: ignore[no-any-return]

    async def list_all(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            rows = await conn.fetch(
                "SELECT data FROM entities WHERE kind = $1 ORDER BY created_at",
                self._kind,
            )
            return [
                self._json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                for r in rows
            ]

    async def remove(self, definition_id: str) -> bool:
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.execute(
                "DELETE FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                definition_id,
            )
            return result == "DELETE 1"  # type: ignore[no-any-return]
