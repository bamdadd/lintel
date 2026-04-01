"""NotificationTemplate — reusable notification body templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import NotificationChannel


@dataclass(frozen=True)
class NotificationTemplate:
    """A stored template for rendering notification messages."""

    template_id: str
    name: str
    channel: NotificationChannel
    body_template: str
    subject_template: str = ""
