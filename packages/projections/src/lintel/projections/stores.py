"""Projection state stores — in-memory and Postgres implementations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

    from lintel.projections.types import ProjectionState


class InMemoryProjectionStore:
    """Dict-backed projection store for testing."""

    def __init__(self) -> None:
        self._states: dict[str, ProjectionState] = {}

    async def save(self, state: ProjectionState) -> None:
        self._states[state.projection_name] = state

    async def load(self, projection_name: str) -> ProjectionState | None:
        return self._states.get(projection_name)

    async def load_all(self) -> list[ProjectionState]:
        return list(self._states.values())

    async def delete(self, projection_name: str) -> None:
        self._states.pop(projection_name, None)


class PostgresProjectionStore:
    """Postgres-backed projection store using the shared entities table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.persistence.dict_store import PostgresDictStore

        self._inner = PostgresDictStore(pool, kind="projection_state")

    async def save(self, state: ProjectionState) -> None:
        data = asdict(state)
        data["updated_at"] = data["updated_at"].isoformat()
        await self._inner.put(state.projection_name, data)

    async def load(self, projection_name: str) -> ProjectionState | None:
        from lintel.projections.types import ProjectionState as _ProjectionState

        data = await self._inner.get(projection_name)
        if data is None:
            return None
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return _ProjectionState(**data)

    async def load_all(self) -> list[ProjectionState]:
        from lintel.projections.types import ProjectionState as _ProjectionState

        rows = await self._inner.list_all()
        for r in rows:
            r["updated_at"] = datetime.fromisoformat(r["updated_at"])
        return [_ProjectionState(**r) for r in rows]

    async def delete(self, projection_name: str) -> None:
        await self._inner.remove(projection_name)
