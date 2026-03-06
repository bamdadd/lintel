"""Generic Postgres-backed CRUD store for frozen dataclasses."""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, TypeVar, overload

if TYPE_CHECKING:
    import asyncpg

T = TypeVar("T")


def _serialize(obj: object) -> dict[str, Any]:
    """Serialize a frozen dataclass to a JSON-safe dict."""
    data = dataclasses.asdict(obj)  # type: ignore[arg-type]
    # Convert frozensets and tuples for JSON compatibility
    for key, value in data.items():
        if isinstance(value, (frozenset, tuple)):
            data[key] = list(value)
    return data


class PostgresCrudStore:
    """Generic CRUD store backed by the ``entities`` table.

    Works with frozen dataclasses. Stores them as JSONB and reconstructs
    them on read using the provided ``factory`` callable.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        kind: str,
        id_field: str,
        factory: type[Any],
    ) -> None:
        self._pool = pool
        self._kind = kind
        self._id_field = id_field
        self._factory = factory

    def _to_instance(self, data: dict[str, Any]) -> Any:  # noqa: ANN401
        """Reconstruct a dataclass from stored data."""
        # Convert lists back to frozensets/tuples where the factory expects them
        import dataclasses as dc

        hints = {f.name: f.type for f in dc.fields(self._factory)}
        for key, value in list(data.items()):
            hint = hints.get(key, "")
            hint_str = str(hint)
            if isinstance(value, list):
                if "frozenset" in hint_str:
                    data[key] = frozenset(
                        tuple(item) if isinstance(item, list) else item for item in value
                    )
                elif "tuple" in hint_str:
                    data[key] = tuple(value)
        return self._factory(**data)

    async def add(self, entity: Any) -> None:  # noqa: ANN401
        """Insert a new entity. Raises ValueError if it already exists."""
        data = _serialize(entity)
        entity_id = data[self._id_field]
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT 1 FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                str(entity_id),
            )
            if existing:
                msg = f"{self._kind} {entity_id} already exists"
                raise ValueError(msg)
            await conn.execute(
                """
                INSERT INTO entities (kind, entity_id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                """,
                self._kind,
                str(entity_id),
                json.dumps(data, default=str),
            )

    @overload
    async def get(self, entity_id: str, *, raw: bool = ...) -> Any: ...  # noqa: ANN401

    async def get(self, entity_id: str, *, raw: bool = False) -> Any:
        """Get a single entity by ID. Returns None if not found."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                str(entity_id),
            )
            if row is None:
                return None
            data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            if raw:
                return data
            return self._to_instance(data)

    async def list_all(self, **filters: Any) -> list[Any]:  # noqa: ANN401
        """List all entities, optionally filtered by JSONB fields."""
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
                self._to_instance(
                    json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                )
                for r in rows
            ]

    async def update(self, entity: Any) -> None:  # noqa: ANN401
        """Update an existing entity."""
        data = _serialize(entity)
        entity_id = data[self._id_field]
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE entities SET data = $3::jsonb, updated_at = now()
                WHERE kind = $1 AND entity_id = $2
                """,
                self._kind,
                str(entity_id),
                json.dumps(data, default=str),
            )
            if result == "UPDATE 0":
                msg = f"{self._kind} {entity_id} not found"
                raise KeyError(msg)

    async def remove(self, entity_id: str) -> None:
        """Delete an entity."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM entities WHERE kind = $1 AND entity_id = $2",
                self._kind,
                str(entity_id),
            )
            if result == "DELETE 0":
                msg = f"{self._kind} {entity_id} not found"
                raise KeyError(msg)
