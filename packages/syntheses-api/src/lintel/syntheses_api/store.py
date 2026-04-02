"""In-memory synthesis store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


class SynthesisStore:
    """In-memory store for syntheses."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _to_dict(entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entity)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        return data

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        self._data[data["synthesis_id"]] = data
        return data

    async def get(self, synthesis_id: str) -> dict[str, Any] | None:
        return self._data.get(synthesis_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if project_id in d.get("project_ids", [])]

    async def list_by_min_confidence(self, min_confidence: float) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("confidence_score", 0.0) >= min_confidence]

    async def remove(self, synthesis_id: str) -> bool:
        return self._data.pop(synthesis_id, None) is not None
