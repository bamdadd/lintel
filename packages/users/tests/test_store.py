"""Tests for InMemoryUserStore."""

from lintel.domain.types import User
from lintel.users.store import InMemoryUserStore


class TestSlackIdLookup:
    """Tests for get_by_slack_id reverse index."""

    async def test_get_by_slack_id_returns_user(self) -> None:
        store = InMemoryUserStore()
        user = User(user_id="u-1", name="Alice", slack_user_id="U12345")
        await store.add(user)
        result = await store.get_by_slack_id("U12345")
        assert result is not None
        assert result.user_id == "u-1"

    async def test_get_by_slack_id_returns_none_when_not_found(self) -> None:
        store = InMemoryUserStore()
        result = await store.get_by_slack_id("U99999")
        assert result is None

    async def test_get_by_slack_id_ignores_empty_slack_id(self) -> None:
        store = InMemoryUserStore()
        user = User(user_id="u-1", name="Alice", slack_user_id="")
        await store.add(user)
        result = await store.get_by_slack_id("")
        assert result is None

    async def test_update_reindexes_slack_id(self) -> None:
        store = InMemoryUserStore()
        user = User(user_id="u-1", name="Alice", slack_user_id="U12345")
        await store.add(user)
        updated = User(user_id="u-1", name="Alice", slack_user_id="U99999")
        await store.update(updated)
        assert await store.get_by_slack_id("U12345") is None
        result = await store.get_by_slack_id("U99999")
        assert result is not None
        assert result.user_id == "u-1"

    async def test_remove_cleans_up_slack_index(self) -> None:
        store = InMemoryUserStore()
        user = User(user_id="u-1", name="Alice", slack_user_id="U12345")
        await store.add(user)
        await store.remove("u-1")
        assert await store.get_by_slack_id("U12345") is None
