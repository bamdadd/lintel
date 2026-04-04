"""In-memory auth user and session stores."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.auth.types import AuthSession, AuthUser


class InMemoryAuthUserStore:
    """Simple in-memory store for auth users, keyed by email."""

    def __init__(self) -> None:
        self._by_id: dict[str, AuthUser] = {}
        self._by_email: dict[str, AuthUser] = {}
        self._by_slack_id: dict[str, str] = {}  # slack_user_id → user_id

    async def add(self, user: AuthUser) -> None:
        self._by_id[user.user_id] = user
        self._by_email[user.email] = user
        if user.slack_user_id:
            self._by_slack_id[user.slack_user_id] = user.user_id

    async def get_by_id(self, user_id: str) -> AuthUser | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> AuthUser | None:
        return self._by_email.get(email)

    async def get_by_slack_id(self, slack_user_id: str) -> AuthUser | None:
        """Look up an auth user by their Slack user ID."""
        user_id = self._by_slack_id.get(slack_user_id)
        if user_id is None:
            return None
        return self._by_id.get(user_id)


class InMemorySessionStore:
    """In-memory store for auth sessions, keyed by session_id."""

    def __init__(self) -> None:
        self._by_id: dict[str, AuthSession] = {}
        self._by_user: dict[str, list[str]] = {}  # user_id → [session_id, ...]
        self._by_jti: dict[str, str] = {}  # jti → session_id

    async def create(self, session: AuthSession) -> None:
        self._by_id[session.session_id] = session
        self._by_user.setdefault(session.user_id, []).append(session.session_id)
        if session.refresh_token_jti:
            self._by_jti[session.refresh_token_jti] = session.session_id

    async def get(self, session_id: str) -> AuthSession | None:
        return self._by_id.get(session_id)

    async def get_by_jti(self, jti: str) -> AuthSession | None:
        sid = self._by_jti.get(jti)
        if sid is None:
            return None
        return self._by_id.get(sid)

    async def list_for_user(self, user_id: str) -> list[AuthSession]:
        sids = self._by_user.get(user_id, [])
        return [self._by_id[s] for s in sids if s in self._by_id]

    async def revoke(self, session_id: str, revoked_at: str) -> bool:
        """Revoke a session. Returns True if the session existed."""
        from dataclasses import replace

        session = self._by_id.get(session_id)
        if session is None:
            return False
        revoked = replace(session, revoked=True, revoked_at=revoked_at)
        self._by_id[session_id] = revoked
        return True

    async def revoke_all_for_user(self, user_id: str, revoked_at: str) -> int:
        """Revoke all sessions for a user. Returns count revoked."""
        count = 0
        for sid in self._by_user.get(user_id, []):
            if await self.revoke(sid, revoked_at):
                count += 1
        return count
