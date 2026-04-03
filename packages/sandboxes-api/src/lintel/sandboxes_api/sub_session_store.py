"""In-memory store for agent sub-sessions."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import SubSession, SubSessionStatus


def _sub_session_to_dict(s: SubSession) -> dict[str, Any]:
    d = asdict(s)
    d["created_at"] = s.created_at.isoformat()
    d["completed_at"] = s.completed_at.isoformat() if s.completed_at else None
    return d


class InMemorySubSessionStore:
    """In-memory store for agent sub-sessions."""

    def __init__(self) -> None:
        self._items: dict[str, SubSession] = {}

    async def get(self, session_id: str) -> dict[str, Any] | None:
        item = self._items.get(session_id)
        return _sub_session_to_dict(item) if item else None

    async def list_by_pipeline(
        self,
        parent_pipeline_run_id: str,
        *,
        status: SubSessionStatus | None = None,
    ) -> list[dict[str, Any]]:
        items = (
            s
            for s in self._items.values()
            if s.parent_pipeline_run_id == parent_pipeline_run_id
            and (status is None or s.status == status)
        )
        return [
            _sub_session_to_dict(s) for s in sorted(items, key=lambda s: s.created_at, reverse=True)
        ]

    async def add(self, sub_session: SubSession) -> dict[str, Any]:
        self._items[sub_session.session_id] = sub_session
        return _sub_session_to_dict(sub_session)

    async def update(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        item = self._items.get(session_id)
        if item is None:
            return None
        data = asdict(item)
        data.update(updates)
        updated = SubSession(**data)
        self._items[session_id] = updated
        return _sub_session_to_dict(updated)

    async def remove(self, session_id: str) -> bool:
        if session_id not in self._items:
            return False
        del self._items[session_id]
        return True
