"""In-memory tech spec store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import TechSpec


class InMemoryTechSpecStore:
    """Simple in-memory store for tech specs."""

    def __init__(self) -> None:
        self._specs: dict[str, TechSpec] = {}

    async def add(self, spec: TechSpec) -> None:
        self._specs[spec.id] = spec

    async def get(self, spec_id: str) -> TechSpec | None:
        return self._specs.get(spec_id)

    async def list_all(self, *, project_id: str | None = None) -> list[TechSpec]:
        specs = list(self._specs.values())
        if project_id is not None:
            specs = [s for s in specs if s.project_id == project_id]
        return specs

    async def update(self, spec: TechSpec) -> None:
        self._specs[spec.id] = spec

    async def remove(self, spec_id: str) -> None:
        del self._specs[spec_id]
