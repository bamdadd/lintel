"""In-memory store for background agent sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    import asyncio


class SessionStatus(Enum):
    """Lifecycle status of a background agent session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LogEntry:
    """A single log line from a background session."""

    timestamp: float
    level: str
    message: str


@dataclass
class BackgroundSession:
    """State of a single background agent session."""

    session_id: str
    agent_role: str
    task: str
    status: SessionStatus = SessionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    logs: list[LogEntry] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class InMemoryBackgroundSessionStore:
    """In-memory store for background agent sessions.

    Tracks session lifecycle and logs. The actual async task references
    are held separately so they don't leak into serialisation.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BackgroundSession] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def create(
        self,
        agent_role: str,
        task_description: str,
        config: dict[str, Any] | None = None,
    ) -> BackgroundSession:
        session_id = str(uuid4())
        session = BackgroundSession(
            session_id=session_id,
            agent_role=agent_role,
            task=task_description,
            config=config or {},
        )
        self._sessions[session_id] = session
        return session

    async def get(self, session_id: str) -> BackgroundSession | None:
        return self._sessions.get(session_id)

    async def list_all(self) -> list[BackgroundSession]:
        return list(self._sessions.values())

    async def mark_running(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.status = SessionStatus.RUNNING
        session.started_at = time.time()

    async def mark_completed(self, session_id: str, result: dict[str, Any] | None = None) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.status = SessionStatus.COMPLETED
        session.finished_at = time.time()
        session.result = result

    async def mark_failed(self, session_id: str, error: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.status = SessionStatus.FAILED
        session.finished_at = time.time()
        session.error = error

    async def mark_cancelled(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.status = SessionStatus.CANCELLED
        session.finished_at = time.time()

    async def append_log(self, session_id: str, level: str, message: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.logs.append(LogEntry(timestamp=time.time(), level=level, message=message))

    def set_task(self, session_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[session_id] = task

    def get_task(self, session_id: str) -> asyncio.Task[None] | None:
        return self._tasks.get(session_id)

    async def delete(self, session_id: str) -> None:
        task = self._tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
        self._sessions.pop(session_id, None)
