"""Tests for SlackUserResolver."""

from lintel.domain.types import User
from lintel.users.resolver import SlackUserResolver
from lintel.users.store import InMemoryUserStore


class TestSlackUserResolver:
    async def test_resolve_linked_user(self) -> None:
        store = InMemoryUserStore()
        await store.add(User(user_id="u-1", name="Alice", slack_user_id="U12345"))
        resolver = SlackUserResolver(store)
        result = await resolver.resolve("U12345")
        assert result is not None
        assert result.user_id == "u-1"
        assert result.name == "Alice"
        assert result.slack_user_id == "U12345"

    async def test_resolve_unknown_returns_none(self) -> None:
        store = InMemoryUserStore()
        resolver = SlackUserResolver(store)
        result = await resolver.resolve("U99999")
        assert result is None

    async def test_resolve_empty_id_returns_none(self) -> None:
        store = InMemoryUserStore()
        resolver = SlackUserResolver(store)
        result = await resolver.resolve("")
        assert result is None
