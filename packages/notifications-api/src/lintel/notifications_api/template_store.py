"""In-memory notification template store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.notifications.notification_template import NotificationTemplate
    from lintel.domain.types import NotificationChannel


class NotificationTemplateStore:
    """In-memory store for notification templates."""

    def __init__(self) -> None:
        self._templates: dict[str, NotificationTemplate] = {}

    async def add(self, template: NotificationTemplate) -> None:
        self._templates[template.template_id] = template

    async def get(self, template_id: str) -> NotificationTemplate | None:
        return self._templates.get(template_id)

    async def get_by_name_and_channel(
        self,
        name: str,
        channel: NotificationChannel,
    ) -> NotificationTemplate | None:
        for tpl in self._templates.values():
            if tpl.name == name and tpl.channel == channel:
                return tpl
        return None

    async def list_all(self) -> list[NotificationTemplate]:
        return list(self._templates.values())

    async def update(self, template: NotificationTemplate) -> None:
        self._templates[template.template_id] = template

    async def remove(self, template_id: str) -> None:
        self._templates.pop(template_id, None)
