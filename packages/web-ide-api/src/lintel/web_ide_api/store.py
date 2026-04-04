"""In-memory IDE session store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class IDESessionStatus(StrEnum):
    """IDE session lifecycle status."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True)
class IDESession:
    """Represents a hosted IDE session for an agent sandbox."""

    session_id: str
    sandbox_id: str
    project_id: str
    workspace_path: str = "/workspace"
    port: int = 8080
    status: IDESessionStatus = IDESessionStatus.STARTING
    proxy_url: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )


class InMemoryIDESessionStore:
    """Simple in-memory store for IDE sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, IDESession] = {}

    async def add(self, session: IDESession) -> None:
        self._sessions[session.session_id] = session

    async def get(self, session_id: str) -> IDESession | None:
        return self._sessions.get(session_id)

    async def list_all(self, project_id: str | None = None) -> list[IDESession]:
        sessions = list(self._sessions.values())
        if project_id is not None:
            sessions = [s for s in sessions if s.project_id == project_id]
        return sessions

    async def update(self, session: IDESession) -> None:
        self._sessions[session.session_id] = session

    async def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
