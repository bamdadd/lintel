"""In-memory work-item store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import WorkItem
from lintel.persistence.data_models import WorkItemData


class WorkItemStore:
    """In-memory work-item store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, work_item: WorkItem) -> None:
        data = asdict(work_item)
        validated = WorkItemData.model_validate(data)
        self._data[work_item.work_item_id] = validated.model_dump()

    async def get(self, work_item_id: str) -> dict[str, Any] | None:
        return self._data.get(work_item_id)

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        items = list(self._data.values())
        if project_id is not None:
            items = [i for i in items if i["project_id"] == project_id]
        return items

    async def update(self, work_item_id: str, data: dict[str, Any]) -> None:
        validated = WorkItemData.model_validate(data)
        self._data[work_item_id] = validated.model_dump()

    async def remove(self, work_item_id: str) -> None:
        self._data.pop(work_item_id, None)
