"""In-memory notification preference store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.notifications.notification_preference import NotificationPreference


class NotificationPreferenceStore:
    """In-memory store for user notification preferences."""

    def __init__(self) -> None:
        self._prefs: dict[str, NotificationPreference] = {}

    async def add(self, pref: NotificationPreference) -> None:
        self._prefs[pref.preference_id] = pref

    async def get(self, preference_id: str) -> NotificationPreference | None:
        return self._prefs.get(preference_id)

    async def list_all(
        self,
        *,
        user_id: str | None = None,
    ) -> list[NotificationPreference]:
        prefs = list(self._prefs.values())
        if user_id is not None:
            prefs = [p for p in prefs if p.user_id == user_id]
        return prefs

    async def update(self, pref: NotificationPreference) -> None:
        self._prefs[pref.preference_id] = pref

    async def remove(self, preference_id: str) -> None:
        self._prefs.pop(preference_id, None)
