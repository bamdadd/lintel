"""In-memory browser extension modification store."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.browser_extension_api.types import ComponentModification


def _to_dict(m: ComponentModification) -> dict[str, Any]:
    d = asdict(m)
    d["created_at"] = m.created_at.isoformat()
    d["updated_at"] = m.updated_at.isoformat()
    return d


class InMemoryComponentModificationStore:
    """Simple in-memory store for component modifications."""

    def __init__(self) -> None:
        self._items: dict[str, ComponentModification] = {}

    async def add(self, modification: ComponentModification) -> dict[str, Any]:
        self._items[modification.id] = modification
        return _to_dict(modification)

    async def get(self, modification_id: str) -> dict[str, Any] | None:
        m = self._items.get(modification_id)
        if m is None:
            return None
        return _to_dict(m)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(m) for m in self._items.values()]

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [_to_dict(m) for m in self._items.values() if m.project_id == project_id]

    async def update(self, modification_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        from lintel.browser_extension_api.types import ComponentModification

        m = self._items.get(modification_id)
        if m is None:
            return None
        data = asdict(m)
        data.update(updates)
        updated = ComponentModification(**data)
        self._items[modification_id] = updated
        return _to_dict(updated)

    async def remove(self, modification_id: str) -> bool:
        if modification_id not in self._items:
            return False
        del self._items[modification_id]
        return True
