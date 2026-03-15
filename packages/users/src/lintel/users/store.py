"""In-memory user store."""

from lintel.domain.types import User


class InMemoryUserStore:
    """Simple in-memory store for users."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def add(self, user: User) -> None:
        self._users[user.user_id] = user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def list_all(self) -> list[User]:
        return list(self._users.values())

    async def update(self, user: User) -> None:
        self._users[user.user_id] = user

    async def remove(self, user_id: str) -> None:
        del self._users[user_id]
