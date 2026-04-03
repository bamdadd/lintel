"""Sub-session manager for parallel agent research across repos."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import structlog

from lintel.agents.types import SubSession, SubSessionStatus

logger = structlog.get_logger()

DEFAULT_MAX_SUB_SESSIONS = 5


class SubSessionManager:
    """Manages child research sessions spawned by a parent agent.

    Sub-sessions are in-memory — they live for the duration of a single
    pipeline run and allow an agent to fan out research across multiple
    repositories in parallel.
    """

    def __init__(self, max_sub_sessions: int = DEFAULT_MAX_SUB_SESSIONS) -> None:
        self._sessions: dict[str, SubSession] = {}
        self._max_sub_sessions = max_sub_sessions

    def spawn(self, parent_session_id: str, repo: str, prompt: str) -> SubSession:
        """Create a new pending sub-session.

        Raises ``ValueError`` if the maximum number of sub-sessions for
        this parent has been reached.
        """
        parent_count = sum(
            1 for s in self._sessions.values() if s.parent_session_id == parent_session_id
        )
        if parent_count >= self._max_sub_sessions:
            msg = (
                f"Max sub-sessions ({self._max_sub_sessions}) reached "
                f"for parent {parent_session_id}"
            )
            raise ValueError(msg)

        session = SubSession(
            session_id=uuid4().hex,
            parent_session_id=parent_session_id,
            repo=repo,
            prompt=prompt,
        )
        self._sessions[session.session_id] = session
        logger.info(
            "sub_session.spawned",
            session_id=session.session_id,
            parent=parent_session_id,
            repo=repo,
        )
        return session

    def get(self, session_id: str) -> SubSession | None:
        """Get a sub-session by ID."""
        return self._sessions.get(session_id)

    def list_for_parent(self, parent_session_id: str) -> list[SubSession]:
        """List all sub-sessions belonging to a parent."""
        return [s for s in self._sessions.values() if s.parent_session_id == parent_session_id]

    def list_all(self) -> list[SubSession]:
        """List all sub-sessions."""
        return list(self._sessions.values())

    def mark_running(self, session_id: str) -> SubSession:
        """Transition a sub-session to running status."""
        session = self._sessions[session_id]
        updated = replace(session, status=SubSessionStatus.RUNNING)
        self._sessions[session_id] = updated
        return updated

    def mark_completed(self, session_id: str, result: str) -> SubSession:
        """Transition a sub-session to completed with a result."""
        session = self._sessions[session_id]
        updated = replace(session, status=SubSessionStatus.COMPLETED, result=result)
        self._sessions[session_id] = updated
        logger.info("sub_session.completed", session_id=session_id, result_len=len(result))
        return updated

    def mark_failed(self, session_id: str, error: str) -> SubSession:
        """Transition a sub-session to failed with an error message."""
        session = self._sessions[session_id]
        updated = replace(session, status=SubSessionStatus.FAILED, error=error)
        self._sessions[session_id] = updated
        logger.warning("sub_session.failed", session_id=session_id, error=error)
        return updated
