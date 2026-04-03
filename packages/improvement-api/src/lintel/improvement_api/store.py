"""In-memory stores for improvement API."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.improvement_api.types import ImprovementEntry


def _to_dict(entry: ImprovementEntry) -> dict[str, Any]:
    d = asdict(entry)
    d["affected_run_ids"] = list(entry.affected_run_ids)
    d["created_at"] = entry.created_at.isoformat()
    return d


def _reconstruct(data: dict[str, Any]) -> ImprovementEntry:
    if isinstance(data.get("affected_run_ids"), list):
        data["affected_run_ids"] = tuple(data["affected_run_ids"])
    return ImprovementEntry(**data)


class InMemoryImprovementStore:
    """In-memory store for improvement ledger entries."""

    def __init__(self) -> None:
        self._items: dict[str, ImprovementEntry] = {}

    async def add(self, entry: ImprovementEntry) -> dict[str, Any]:
        self._items[entry.entry_id] = entry
        return _to_dict(entry)

    async def get(self, entry_id: str) -> dict[str, Any] | None:
        item = self._items.get(entry_id)
        if item is None:
            return None
        return _to_dict(item)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(e) for e in self._items.values()]

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [_to_dict(e) for e in self._items.values() if e.project_id == project_id]

    async def update(self, entry_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        entry = self._items.get(entry_id)
        if entry is None:
            return None
        data = asdict(entry)
        data.update(updates)
        updated = _reconstruct(data)
        self._items[entry_id] = updated
        return _to_dict(updated)

    async def remove(self, entry_id: str) -> bool:
        if entry_id not in self._items:
            return False
        del self._items[entry_id]
        return True
