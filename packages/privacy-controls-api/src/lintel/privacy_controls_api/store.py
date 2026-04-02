"""In-memory privacy controls store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import MetricVisibility, PrivacyPreference


def _visibility_to_dict(v: MetricVisibility) -> dict[str, Any]:
    """Convert a MetricVisibility dataclass to a JSON-friendly dict."""
    d = asdict(v)
    d["created_at"] = v.created_at.isoformat()
    d["updated_at"] = v.updated_at.isoformat()
    d["allowed_viewers"] = list(v.allowed_viewers)
    return d


def _preference_to_dict(p: PrivacyPreference) -> dict[str, Any]:
    """Convert a PrivacyPreference dataclass to a JSON-friendly dict."""
    d = asdict(p)
    d["created_at"] = p.created_at.isoformat()
    d["updated_at"] = p.updated_at.isoformat()
    d["opt_out_metrics"] = list(p.opt_out_metrics)
    return d


class InMemoryVisibilityStore:
    """Simple in-memory store for metric visibility rules."""

    def __init__(self) -> None:
        self._items: dict[str, MetricVisibility] = {}

    async def get(self, visibility_id: str) -> dict[str, Any] | None:
        item = self._items.get(visibility_id)
        if item is None:
            return None
        return _visibility_to_dict(item)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_visibility_to_dict(v) for v in self._items.values()]

    async def add(self, item: MetricVisibility) -> dict[str, Any]:
        self._items[item.visibility_id] = item
        return _visibility_to_dict(item)

    async def update(
        self,
        visibility_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        item = self._items.get(visibility_id)
        if item is None:
            return None
        data = asdict(item)
        data.update(updates)
        if "allowed_viewers" in data and isinstance(data["allowed_viewers"], list):
            data["allowed_viewers"] = tuple(data["allowed_viewers"])
        updated = MetricVisibility(**data)
        self._items[visibility_id] = updated
        return _visibility_to_dict(updated)

    async def remove(self, visibility_id: str) -> bool:
        if visibility_id not in self._items:
            return False
        del self._items[visibility_id]
        return True


class InMemoryPreferenceStore:
    """Simple in-memory store for privacy preferences (keyed by user_id)."""

    def __init__(self) -> None:
        self._items: dict[str, PrivacyPreference] = {}

    async def get(self, user_id: str) -> dict[str, Any] | None:
        item = self._items.get(user_id)
        if item is None:
            return None
        return _preference_to_dict(item)

    async def put(self, item: PrivacyPreference) -> dict[str, Any]:
        self._items[item.user_id] = item
        return _preference_to_dict(item)
