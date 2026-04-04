"""In-memory multiplayer session store."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.domain.types import Session


class InMemorySessionStore:
    """Simple in-memory store for multiplayer sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    async def add(self, session: Session) -> dict[str, Any]:
        data = asdict(session)
        data["participants"] = [asdict(p) for p in session.participants]
        self._sessions[session.session_id] = data
        return data

    async def get(self, session_id: str) -> dict[str, Any] | None:
        return self._sessions.get(session_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._sessions.values())

    async def update(self, session_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = self._sessions.get(session_id)
        if existing is None:
            return None
        existing.update(data)
        return existing
