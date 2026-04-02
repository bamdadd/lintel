"""In-memory user store."""

from lintel.domain.types import User


class InMemoryUserStore:
    """Simple in-memory store for users."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._by_slack_id: dict[str, str] = {}  # slack_user_id → user_id

    async def add(self, user: User) -> None:
        self._users[user.user_id] = user
        if user.slack_user_id:
            self._by_slack_id[user.slack_user_id] = user.user_id

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def get_by_slack_id(self, slack_user_id: str) -> User | None:
        """Look up a user by their Slack user ID."""
        user_id = self._by_slack_id.get(slack_user_id)
        if user_id is None:
            return None
        return self._users.get(user_id)

    async def list_all(self) -> list[User]:
        return list(self._users.values())

    async def update(self, user: User) -> None:
        old = self._users.get(user.user_id)
        if old and old.slack_user_id and old.slack_user_id != user.slack_user_id:
            self._by_slack_id.pop(old.slack_user_id, None)
        self._users[user.user_id] = user
        if user.slack_user_id:
            self._by_slack_id[user.slack_user_id] = user.user_id

    async def remove(self, user_id: str) -> None:
        user = self._users.get(user_id)
        if user and user.slack_user_id:
            self._by_slack_id.pop(user.slack_user_id, None)
        del self._users[user_id]
