"""In-memory playbook store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


class PlaybookStore:
    """In-memory store for playbooks."""

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
        self._data[data["playbook_id"]] = data
        return data

    async def get(self, playbook_id: str) -> dict[str, Any] | None:
        return self._data.get(playbook_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def remove(self, playbook_id: str) -> bool:
        return self._data.pop(playbook_id, None) is not None
