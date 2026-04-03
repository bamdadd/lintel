"""Session lifecycle manager for sandbox hibernation, resume, and cost tracking."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from lintel.sandbox.errors import (
    SandboxHibernatedError,
    SandboxNotFoundError,
    SessionAlreadyInStateError,
)
from lintel.sandbox.types import (
    SessionCost,
    SessionLifecycle,
    SessionState,
    TimeoutConfig,
)


class SessionLifecycleManager:
    """Manages session state transitions, idle timeouts, and cost accumulation.

    This is a pure domain service — it does not interact with Docker or snapshots.
    API routes orchestrate the actual container stop/start and snapshot creation
    around the state transitions managed here.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionLifecycle] = {}

    def register(
        self,
        sandbox_id: str,
        timeout_config: TimeoutConfig | None = None,
    ) -> SessionLifecycle:
        """Register a new sandbox session for lifecycle tracking."""
        now = datetime.now(UTC)
        session = SessionLifecycle(
            sandbox_id=sandbox_id,
            timeout_config=timeout_config or TimeoutConfig(),
            created_at=now,
            last_activity_at=now,
        )
        self._sessions[sandbox_id] = session
        return session

    def get(self, sandbox_id: str) -> SessionLifecycle:
        """Get session lifecycle state. Raises SandboxNotFoundError if not tracked."""
        session = self._sessions.get(sandbox_id)
        if session is None:
            raise SandboxNotFoundError(sandbox_id)
        return session

    def get_or_none(self, sandbox_id: str) -> SessionLifecycle | None:
        """Get session lifecycle state, or None if not tracked."""
        return self._sessions.get(sandbox_id)

    def list_all(self) -> list[SessionLifecycle]:
        """List all tracked sessions."""
        return list(self._sessions.values())

    def record_activity(self, sandbox_id: str) -> SessionLifecycle:
        """Update last_activity_at timestamp. Call on every sandbox operation."""
        session = self.get(sandbox_id)
        if session.state == SessionState.HIBERNATED:
            raise SandboxHibernatedError(sandbox_id)
        updated = replace(session, last_activity_at=datetime.now(UTC))
        self._sessions[sandbox_id] = updated
        return updated

    def hibernate(self, sandbox_id: str, snapshot_id: str) -> SessionLifecycle:
        """Transition session to hibernated state."""
        session = self.get(sandbox_id)
        if session.state == SessionState.HIBERNATED:
            raise SessionAlreadyInStateError(sandbox_id, "hibernated", "hibernated")
        if session.state == SessionState.TERMINATED:
            raise SessionAlreadyInStateError(sandbox_id, "terminated", "hibernated")

        now = datetime.now(UTC)
        cost = self._accumulate_cost(session, now)
        updated = replace(
            session,
            state=SessionState.HIBERNATED,
            snapshot_id=snapshot_id,
            hibernated_at=now,
            cost=cost,
        )
        self._sessions[sandbox_id] = updated
        return updated

    def resume(self, sandbox_id: str) -> SessionLifecycle:
        """Transition session from hibernated back to resumed/running."""
        session = self.get(sandbox_id)
        if session.state != SessionState.HIBERNATED:
            raise SessionAlreadyInStateError(sandbox_id, session.state.value, "resumed")

        now = datetime.now(UTC)
        updated = replace(
            session,
            state=SessionState.RESUMED,
            resumed_at=now,
            last_activity_at=now,
        )
        self._sessions[sandbox_id] = updated
        return updated

    def terminate(self, sandbox_id: str) -> SessionLifecycle:
        """Transition session to terminated state."""
        session = self.get(sandbox_id)
        if session.state == SessionState.TERMINATED:
            raise SessionAlreadyInStateError(sandbox_id, "terminated", "terminated")

        now = datetime.now(UTC)
        cost = self._accumulate_cost(session, now)
        updated = replace(
            session,
            state=SessionState.TERMINATED,
            terminated_at=now,
            cost=cost,
        )
        self._sessions[sandbox_id] = updated
        return updated

    def remove(self, sandbox_id: str) -> None:
        """Remove a session from tracking."""
        self._sessions.pop(sandbox_id, None)

    def update_timeout_config(
        self,
        sandbox_id: str,
        timeout_config: TimeoutConfig,
    ) -> SessionLifecycle:
        """Update timeout configuration for a session."""
        session = self.get(sandbox_id)
        updated = replace(session, timeout_config=timeout_config)
        self._sessions[sandbox_id] = updated
        return updated

    def check_idle_sessions(self) -> list[str]:
        """Return sandbox IDs that have exceeded their idle timeout.

        Callers should hibernate these sessions.
        """
        now = datetime.now(UTC)
        idle_ids: list[str] = []
        for session in self._sessions.values():
            if session.state not in (SessionState.RUNNING, SessionState.RESUMED):
                continue
            elapsed = (now - session.last_activity_at).total_seconds()
            if elapsed >= session.timeout_config.idle_timeout_seconds:
                idle_ids.append(session.sandbox_id)
        return idle_ids

    def check_expired_sessions(self) -> list[str]:
        """Return sandbox IDs that have exceeded their max lifetime.

        Callers should terminate these sessions.
        """
        now = datetime.now(UTC)
        expired_ids: list[str] = []
        for session in self._sessions.values():
            if session.state == SessionState.TERMINATED:
                continue
            elapsed = (now - session.created_at).total_seconds()
            if elapsed >= session.timeout_config.max_lifetime_seconds:
                expired_ids.append(session.sandbox_id)
        return expired_ids

    @staticmethod
    def _accumulate_cost(session: SessionLifecycle, now: datetime) -> SessionCost:
        """Add cost for the time since last_activity_at (approximation)."""
        elapsed = max(0.0, (now - session.last_activity_at).total_seconds())
        return SessionCost(
            cpu_seconds=session.cost.cpu_seconds + elapsed,
            memory_mb_seconds=session.cost.memory_mb_seconds + elapsed * 4096,
            storage_mb_seconds=session.cost.storage_mb_seconds + elapsed * 1024,
        )
