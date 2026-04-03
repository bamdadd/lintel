"""Tests for in-memory digest stores."""

from datetime import UTC, datetime

from lintel.digest_api.store import InMemoryDigestConfigStore, InMemoryDigestStore
from lintel.digest_api.types import Digest, DigestConfig


class TestInMemoryDigestStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryDigestStore()
        digest = Digest(
            id="d-1",
            project_id="p-1",
            team_id="t-1",
            period_start=datetime(2026, 3, 24, tzinfo=UTC),
            period_end=datetime(2026, 3, 31, tzinfo=UTC),
            summary="Good week",
        )
        await store.add(digest)
        result = await store.get("d-1")
        assert result is not None
        assert result.summary == "Good week"

    async def test_get_returns_none_when_missing(self) -> None:
        store = InMemoryDigestStore()
        assert await store.get("nope") is None

    async def test_list_all(self) -> None:
        store = InMemoryDigestStore()
        d1 = Digest(
            id="d-1",
            project_id="p-1",
            team_id="t-1",
            period_start=datetime(2026, 3, 24, tzinfo=UTC),
            period_end=datetime(2026, 3, 31, tzinfo=UTC),
            summary="Week 1",
        )
        d2 = Digest(
            id="d-2",
            project_id="p-1",
            team_id="t-1",
            period_start=datetime(2026, 3, 31, tzinfo=UTC),
            period_end=datetime(2026, 4, 7, tzinfo=UTC),
            summary="Week 2",
        )
        await store.add(d1)
        await store.add(d2)
        items = await store.list_all()
        assert len(items) == 2

    async def test_remove(self) -> None:
        store = InMemoryDigestStore()
        digest = Digest(
            id="d-1",
            project_id="p-1",
            team_id="t-1",
            period_start=datetime(2026, 3, 24, tzinfo=UTC),
            period_end=datetime(2026, 3, 31, tzinfo=UTC),
            summary="Bye",
        )
        await store.add(digest)
        await store.remove("d-1")
        assert await store.get("d-1") is None


class TestInMemoryDigestConfigStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryDigestConfigStore()
        config = DigestConfig(id="dc-1", project_id="p-1", schedule="weekly")
        await store.add(config)
        result = await store.get("dc-1")
        assert result is not None
        assert result.schedule == "weekly"

    async def test_update(self) -> None:
        store = InMemoryDigestConfigStore()
        config = DigestConfig(id="dc-1", project_id="p-1", schedule="weekly")
        await store.add(config)
        updated = DigestConfig(id="dc-1", project_id="p-1", schedule="daily")
        await store.update(updated)
        result = await store.get("dc-1")
        assert result is not None
        assert result.schedule == "daily"

    async def test_remove(self) -> None:
        store = InMemoryDigestConfigStore()
        config = DigestConfig(id="dc-1", project_id="p-1")
        await store.add(config)
        await store.remove("dc-1")
        assert await store.get("dc-1") is None

    async def test_list_all(self) -> None:
        store = InMemoryDigestConfigStore()
        await store.add(DigestConfig(id="dc-1", project_id="p-1"))
        await store.add(DigestConfig(id="dc-2", project_id="p-2"))
        items = await store.list_all()
        assert len(items) == 2
