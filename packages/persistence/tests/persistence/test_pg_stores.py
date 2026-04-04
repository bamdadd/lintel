"""Tests for Postgres-backed stores in pg_stores.py.

These verify the store interfaces work correctly using an in-memory
mock of PostgresDictStore, so no real database is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock


def _make_pool() -> MagicMock:
    """Create a mock asyncpg.Pool that returns a mock connection."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm
    return pool


class TestPostgresDriftRuleStore:
    async def test_init(self) -> None:
        from lintel.persistence.pg_stores import PostgresDriftRuleStore

        store = PostgresDriftRuleStore(_make_pool())
        assert store._id_field == "rule_id"


class TestPostgresCodingRuleStore:
    async def test_init(self) -> None:
        from lintel.persistence.pg_stores import PostgresCodingRuleStore

        store = PostgresCodingRuleStore(_make_pool())
        assert store._id_field == "rule_id"


class TestPostgresAgentSkillBindingStore:
    async def test_init(self) -> None:
        from lintel.persistence.pg_stores import PostgresAgentSkillBindingStore

        store = PostgresAgentSkillBindingStore(_make_pool())
        assert store._id_field == "binding_id"


class TestPostgresCodebaseIndexStore:
    async def test_add_and_get_index(self) -> None:
        from lintel.persistence.pg_stores import PostgresCodebaseIndexStore

        pool = _make_pool()
        store = PostgresCodebaseIndexStore(pool)

        # Mock the DictStore's put and get
        store._indices = MagicMock()
        store._indices.put = AsyncMock()
        store._indices.get = AsyncMock(return_value={"index_id": "idx1", "project_id": "p1"})

        data = {"index_id": "idx1", "project_id": "p1"}
        result = await store.add_index(data)
        assert result["index_id"] == "idx1"

        got = await store.get_index("idx1")
        assert got is not None
        assert got["index_id"] == "idx1"

    async def test_search(self) -> None:
        from lintel.persistence.pg_stores import PostgresCodebaseIndexStore

        pool = _make_pool()
        store = PostgresCodebaseIndexStore(pool)
        store._entries = MagicMock()
        store._entries.list_all = AsyncMock(
            return_value=[
                {
                    "entry_id": "e1",
                    "index_id": "idx1",
                    "content": "hello world",
                    "file_path": "a.py",
                },
                {
                    "entry_id": "e2",
                    "index_id": "idx1",
                    "content": "goodbye",
                    "file_path": "b.py",
                },
            ]
        )
        results = await store.search("idx1", "hello")
        assert len(results) == 1
        assert results[0]["entry_id"] == "e1"


class TestPostgresTrustScoreStore:
    async def test_add_and_get(self) -> None:
        from lintel.persistence.pg_stores import PostgresTrustScoreStore

        pool = _make_pool()
        store = PostgresTrustScoreStore(pool)
        store._scores = MagicMock()
        store._scores.put = AsyncMock()
        store._scores.get = AsyncMock(return_value={"agent_id": "a1", "score": 0.8})

        @dataclass
        class FakeTrustScore:
            agent_id: str
            score: float

        result = await store.add(FakeTrustScore(agent_id="a1", score=0.8))
        assert result["agent_id"] == "a1"

        got = await store.get("a1")
        assert got is not None
        assert got["score"] == 0.8


class TestPostgresAttachmentStore:
    async def test_init(self) -> None:
        from lintel.persistence.pg_stores import PostgresAttachmentStore

        store = PostgresAttachmentStore(_make_pool())
        assert store._id_field == "attachment_id"


class TestPostgresParsedTestResultStore:
    async def test_save_and_get(self) -> None:
        from lintel.persistence.pg_stores import PostgresParsedTestResultStore

        pool = _make_pool()
        store = PostgresParsedTestResultStore(pool)
        store._store = MagicMock()
        store._store.put = AsyncMock()
        store._store.get = AsyncMock(
            return_value={
                "result_id": "r1",
                "run_id": "run1",
                "project_id": "p1",
                "artifact_id": "a1",
                "total": 5,
            }
        )

        result = await store.save("r1", "run1", "p1", "a1", {"total": 5})
        assert result["result_id"] == "r1"
        assert result["total"] == 5

        got = await store.get("r1")
        assert got is not None


class TestPostgresMCPToolStore:
    async def test_init_and_list(self) -> None:
        from lintel.persistence.pg_stores import PostgresMCPToolStore

        pool = _make_pool()
        store = PostgresMCPToolStore(pool)
        store._store = MagicMock()
        store._store.list_all = AsyncMock(return_value=[])

        result = await store.list_all()
        assert result == []


class TestPostgresMCPToolAllowlistStore:
    async def test_get_by_project(self) -> None:
        from lintel.persistence.pg_stores import PostgresMCPToolAllowlistStore

        pool = _make_pool()
        store = PostgresMCPToolAllowlistStore(pool)
        store._store = MagicMock()
        store._store.list_all = AsyncMock(
            return_value=[{"allowlist_id": "al1", "project_id": "p1"}]
        )

        result = await store.get_by_project("p1")
        assert result is not None
        assert result["allowlist_id"] == "al1"

    async def test_get_by_project_none(self) -> None:
        from lintel.persistence.pg_stores import PostgresMCPToolAllowlistStore

        pool = _make_pool()
        store = PostgresMCPToolAllowlistStore(pool)
        store._store = MagicMock()
        store._store.list_all = AsyncMock(return_value=[])

        result = await store.get_by_project("p1")
        assert result is None
