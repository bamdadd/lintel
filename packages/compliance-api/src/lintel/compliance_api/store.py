"""Generic in-memory compliance store."""

from dataclasses import asdict
from typing import Any


class ComplianceStore:
    """Generic in-memory store for any frozen dataclass with an id field."""

    def __init__(self, id_field: str) -> None:
        self._data: dict[str, Any] = {}
        self._id_field = id_field

    def _to_dict(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entity)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        return data

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        self._data[data[self._id_field]] = data
        return data

    async def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._data.get(entity_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("project_id") == project_id]

    async def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = self._data.get(entity_id)
        if existing is None:
            return None
        merged = {**existing, **data}
        self._data[entity_id] = merged
        return merged

    async def remove(self, entity_id: str) -> bool:
        return self._data.pop(entity_id, None) is not None
