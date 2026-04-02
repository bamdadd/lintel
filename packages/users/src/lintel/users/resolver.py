"""Resolve Slack user IDs to Lintel platform users."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.users.store import InMemoryUserStore

logger = structlog.get_logger()


@dataclass(frozen=True)
class ResolvedUser:
    """Result of resolving a Slack user ID."""

    user_id: str
    name: str
    slack_user_id: str


class SlackUserResolver:
    """Resolves a Slack user ID to a Lintel User via the user store."""

    def __init__(self, user_store: InMemoryUserStore) -> None:
        self._store = user_store

    async def resolve(self, slack_user_id: str) -> ResolvedUser | None:
        """Look up Lintel user by Slack user ID. Returns None if not linked."""
        if not slack_user_id:
            return None
        user = await self._store.get_by_slack_id(slack_user_id)
        if user is None:
            logger.info("slack_user_not_linked", slack_user_id=slack_user_id)
            return None
        return ResolvedUser(
            user_id=user.user_id,
            name=user.name,
            slack_user_id=user.slack_user_id,
        )
