"""In-memory stores for slack notification templates and records."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import SlackNotificationRecord, SlackNotificationTemplate


class InMemorySlackNotificationTemplateStore:
    """Simple in-memory store for notification templates."""

    def __init__(self) -> None:
        self._items: dict[str, SlackNotificationTemplate] = {}

    async def add(self, item: SlackNotificationTemplate) -> None:
        self._items[item.template_id] = item

    async def get(self, template_id: str) -> SlackNotificationTemplate | None:
        return self._items.get(template_id)

    async def list_all(self) -> list[SlackNotificationTemplate]:
        return list(self._items.values())

    async def update(self, item: SlackNotificationTemplate) -> None:
        self._items[item.template_id] = item

    async def remove(self, template_id: str) -> None:
        self._items.pop(template_id, None)


class InMemorySlackNotificationRecordStore:
    """Simple in-memory store for notification records."""

    def __init__(self) -> None:
        self._items: dict[str, SlackNotificationRecord] = {}

    async def add(self, item: SlackNotificationRecord) -> None:
        self._items[item.record_id] = item

    async def get(self, record_id: str) -> SlackNotificationRecord | None:
        return self._items.get(record_id)

    async def list_all(self) -> list[SlackNotificationRecord]:
        return list(self._items.values())

    async def list_by_pipeline(self, pipeline_run_id: str) -> list[SlackNotificationRecord]:
        return [r for r in self._items.values() if r.pipeline_run_id == pipeline_run_id]

    async def list_by_stage(self, stage_name: str) -> list[SlackNotificationRecord]:
        return [r for r in self._items.values() if r.stage_name == stage_name]
