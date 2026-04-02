"""In-memory context attachment store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.context_attachments_api.types import Attachment


def _to_dict(att: Attachment) -> dict[str, Any]:
    """Convert an Attachment dataclass to a JSON-friendly dict."""
    d = asdict(att)
    d["tags"] = list(att.tags)
    d["created_at"] = att.created_at.isoformat()
    d["updated_at"] = att.updated_at.isoformat()
    return d


def _reconstruct(data: dict[str, Any]) -> Attachment:
    """Reconstruct an Attachment from a dict, handling nested types."""
    tags = data.get("tags")
    if isinstance(tags, list):
        data["tags"] = tuple(tags)
    return Attachment(**data)


class InMemoryAttachmentStore:
    """Simple in-memory store for context attachments."""

    def __init__(self) -> None:
        self._items: dict[str, Attachment] = {}

    async def add(self, attachment: Attachment) -> dict[str, Any]:
        self._items[attachment.attachment_id] = attachment
        return _to_dict(attachment)

    async def get(self, attachment_id: str) -> dict[str, Any] | None:
        att = self._items.get(attachment_id)
        if att is None:
            return None
        return _to_dict(att)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_to_dict(att) for att in self._items.values()]

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [_to_dict(att) for att in self._items.values() if att.project_id == project_id]

    async def list_by_target(self, target_type: str, target_id: str) -> list[dict[str, Any]]:
        return [
            _to_dict(att)
            for att in self._items.values()
            if att.target_type == target_type and att.target_id == target_id
        ]

    async def update(self, attachment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        att = self._items.get(attachment_id)
        if att is None:
            return None
        data = asdict(att)
        data.update(updates)
        updated = _reconstruct(data)
        self._items[attachment_id] = updated
        return _to_dict(updated)

    async def remove(self, attachment_id: str) -> bool:
        if attachment_id not in self._items:
            return False
        del self._items[attachment_id]
        return True
