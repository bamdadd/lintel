"""In-memory stores for boards and tags."""

from __future__ import annotations

from typing import Any

from lintel.persistence.data_models import BoardData, TagData


class TagStore:
    """In-memory tag store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        validated = TagData.model_validate(data)
        self._data[validated.tag_id] = validated.model_dump()

    async def get(self, tag_id: str) -> dict[str, Any] | None:
        return self._data.get(tag_id)

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [t for t in self._data.values() if t.get("project_id") == project_id]

    async def update(self, tag_id: str, data: dict[str, Any]) -> None:
        validated = TagData.model_validate(data)
        self._data[tag_id] = validated.model_dump()

    async def remove(self, tag_id: str) -> None:
        self._data.pop(tag_id, None)


class BoardStore:
    """In-memory board store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        validated = BoardData.model_validate(data)
        self._data[validated.board_id] = validated.model_dump()

    async def get(self, board_id: str) -> dict[str, Any] | None:
        return self._data.get(board_id)

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [b for b in self._data.values() if b.get("project_id") == project_id]

    async def update(self, board_id: str, data: dict[str, Any]) -> None:
        validated = BoardData.model_validate(data)
        self._data[board_id] = validated.model_dump()

    async def remove(self, board_id: str) -> None:
        self._data.pop(board_id, None)
