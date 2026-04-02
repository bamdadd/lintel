"""In-memory feedback store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.feedback_api.types import FeedbackTechnicalContext, ProductFeedback


def _to_dict(fb: ProductFeedback) -> dict[str, Any]:
    """Convert a ProductFeedback dataclass to a JSON-friendly dict."""
    d = asdict(fb)
    d["tags"] = list(fb.tags)
    d["technical_context"]["recent_changes"] = list(fb.technical_context.recent_changes)
    d["created_at"] = fb.created_at.isoformat()
    d["updated_at"] = fb.updated_at.isoformat()
    return d


def _reconstruct(data: dict[str, Any]) -> ProductFeedback:
    """Reconstruct a ProductFeedback from a dict, handling nested types."""
    tc = data.get("technical_context")
    if isinstance(tc, dict):
        tc["recent_changes"] = tuple(tc.get("recent_changes", ()))
        data["technical_context"] = FeedbackTechnicalContext(**tc)
    tags = data.get("tags")
    if isinstance(tags, list):
        data["tags"] = tuple(tags)
    return ProductFeedback(**data)


class InMemoryFeedbackStore:
    """Simple in-memory store for product feedback entries."""

    def __init__(self) -> None:
        self._items: dict[str, ProductFeedback] = {}

    async def add(self, feedback: ProductFeedback) -> dict[str, Any]:
        self._items[feedback.feedback_id] = feedback
        return _to_dict(feedback)

    async def get(self, feedback_id: str) -> dict[str, Any] | None:
        fb = self._items.get(feedback_id)
        if fb is None:
            return None
        return _to_dict(fb)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(fb) for fb in self._items.values()]

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [_to_dict(fb) for fb in self._items.values() if fb.project_id == project_id]

    async def update(self, feedback_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        fb = self._items.get(feedback_id)
        if fb is None:
            return None
        data = asdict(fb)
        data.update(updates)
        updated = _reconstruct(data)
        self._items[feedback_id] = updated
        return _to_dict(updated)

    async def remove(self, feedback_id: str) -> bool:
        if feedback_id not in self._items:
            return False
        del self._items[feedback_id]
        return True
