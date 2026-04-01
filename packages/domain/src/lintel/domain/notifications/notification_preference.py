"""NotificationPreference — per-user opt-in/out for event channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.types import NotificationChannel


@dataclass(frozen=True)
class NotificationPreference:
    """Maps a user's preference for receiving notifications on a specific channel/event."""

    preference_id: str
    user_id: str
    event_type: str
    channel: NotificationChannel
    enabled: bool = True
