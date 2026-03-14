"""Tests for PostgresEntityStore, PostgresDictStore with mocked asyncpg pool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from lintel.persistence.dict_store import PostgresDictStore
from lintel.persistence.postgres_entity_store import PostgresEntityStore


def _mock_pool() -> tuple[AsyncMock, AsyncMock]:
    """Return (pool, conn) where pool.acquire() works as async context manager."""
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return pool, conn


# ---------------------------------------------------------------------------
# PostgresEntityStore
# ---------------------------------------------------------------------------


class TestPostgresEntityStore:
    def setup_method(self) -> None:
        self.pool, self.conn = _mock_pool()
        self.store = PostgresEntityStore(self.pool, "test_kind")

    async def test_put_inserts_entity(self) -> None:
        await self.store.put("e1", {"name": "foo"})
        self.conn.execute.assert_called_once()
        call_args = self.conn.execute.call_args[0]
        assert call_args[1] == "test_kind"
        assert call_args[2] == "e1"
        assert json.loads(call_args[3]) == {"name": "foo"}

    async def test_get_returns_entity(self) -> None:
        self.conn.fetchrow.return_value = {"data": json.dumps({"name": "bar"})}
        result = await self.store.get("e1")
        assert result == {"name": "bar"}

    async def test_get_returns_none_when_missing(self) -> None:
        self.conn.fetchrow.return_value = None
        result = await self.store.get("missing")
        assert result is None

    async def test_get_handles_dict_data(self) -> None:
        self.conn.fetchrow.return_value = {"data": {"name": "baz"}}
        result = await self.store.get("e1")
        assert result == {"name": "baz"}

    async def test_list_all(self) -> None:
        self.conn.fetch.return_value = [
            {"data": json.dumps({"id": "1"})},
            {"data": json.dumps({"id": "2"})},
        ]
        result = await self.store.list_all()
        assert len(result) == 2

    async def test_remove_returns_true(self) -> None:
        self.conn.execute.return_value = "DELETE 1"
        result = await self.store.remove("e1")
        assert result is True

    async def test_remove_returns_false(self) -> None:
        self.conn.execute.return_value = "DELETE 0"
        result = await self.store.remove("missing")
        assert result is False

    async def test_find_with_filters(self) -> None:
        self.conn.fetch.return_value = [{"data": json.dumps({"project_id": "p1"})}]
        result = await self.store.find(project_id="p1")
        assert len(result) == 1
        query = self.conn.fetch.call_args[0][0]
        assert "project_id" in query

    async def test_find_ignores_none_filters(self) -> None:
        self.conn.fetch.return_value = []
        await self.store.find(project_id=None)
        query = self.conn.fetch.call_args[0][0]
        assert "project_id" not in query


# ---------------------------------------------------------------------------
# PostgresDictStore
# ---------------------------------------------------------------------------


class TestPostgresDictStore:
    def setup_method(self) -> None:
        self.pool, self.conn = _mock_pool()
        self.store = PostgresDictStore(self.pool, "conversations")

    async def test_put(self) -> None:
        await self.store.put("c1", {"user": "alice"})
        self.conn.execute.assert_called_once()

    async def test_get(self) -> None:
        self.conn.fetchrow.return_value = {"data": json.dumps({"user": "bob"})}
        result = await self.store.get("c1")
        assert result == {"user": "bob"}

    async def test_get_none(self) -> None:
        self.conn.fetchrow.return_value = None
        assert await self.store.get("missing") is None

    async def test_list_all_with_filters(self) -> None:
        self.conn.fetch.return_value = [{"data": {"user_id": "u1"}}]
        result = await self.store.list_all(user_id="u1")
        assert len(result) == 1
        query = self.conn.fetch.call_args[0][0]
        assert "user_id" in query

    async def test_remove(self) -> None:
        self.conn.execute.return_value = "DELETE 1"
        assert await self.store.remove("c1") is True
