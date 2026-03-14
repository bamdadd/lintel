"""Projection state stores — in-memory and Postgres implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.projections import ProjectionState


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
