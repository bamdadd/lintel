"""In-memory auth user store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.auth.types import AuthUser


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
