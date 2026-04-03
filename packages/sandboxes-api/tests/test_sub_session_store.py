"""Tests for InMemorySubSessionStore."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.types import SubSession, SubSessionStatus
from lintel.sandboxes_api.sub_session_store import InMemorySubSessionStore


class TestInMemorySubSessionStore:
    async def test_add_and_get(self) -> None:
        store = InMemorySubSessionStore()
        session = SubSession(
            session_id="s1",
            parent_pipeline_run_id="run-1",
            repo_url="https://github.com/org/repo",
            prompt="research auth patterns",
        )
        result = await store.add(session)
        assert result["session_id"] == "s1"
        assert result["parent_pipeline_run_id"] == "run-1"

        got = await store.get("s1")
        assert got is not None
        assert got["session_id"] == "s1"

    async def test_get_missing(self) -> None:
        store = InMemorySubSessionStore()
        assert await store.get("missing") is None

    async def test_list_by_pipeline_empty(self) -> None:
        store = InMemorySubSessionStore()
        assert await store.list_by_pipeline("run-1") == []

    async def test_list_by_pipeline_filters(self) -> None:
        store = InMemorySubSessionStore()
        await store.add(
            SubSession(session_id="s1", parent_pipeline_run_id="run-1"),
        )
        await store.add(
            SubSession(session_id="s2", parent_pipeline_run_id="run-2"),
        )
        await store.add(
            SubSession(session_id="s3", parent_pipeline_run_id="run-1"),
        )

        result = await store.list_by_pipeline("run-1")
        assert len(result) == 2
        assert {r["session_id"] for r in result} == {"s1", "s3"}

    async def test_list_by_pipeline_status_filter(self) -> None:
        store = InMemorySubSessionStore()
        await store.add(
            SubSession(
                session_id="s1",
                parent_pipeline_run_id="run-1",
                status=SubSessionStatus.RUNNING,
            ),
        )
        await store.add(
            SubSession(
                session_id="s2",
                parent_pipeline_run_id="run-1",
                status=SubSessionStatus.COMPLETED,
            ),
        )

        result = await store.list_by_pipeline("run-1", status=SubSessionStatus.RUNNING)
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"

    async def test_update(self) -> None:
        store = InMemorySubSessionStore()
        await store.add(SubSession(session_id="s1", parent_pipeline_run_id="run-1"))
        updated = await store.update("s1", {"status": SubSessionStatus.COMPLETED, "result": "ok"})
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["result"] == "ok"

    async def test_update_missing(self) -> None:
        store = InMemorySubSessionStore()
        assert await store.update("missing", {"status": "completed"}) is None

    async def test_remove(self) -> None:
        store = InMemorySubSessionStore()
        await store.add(SubSession(session_id="s1", parent_pipeline_run_id="run-1"))
        assert await store.remove("s1") is True
        assert await store.get("s1") is None

    async def test_remove_missing(self) -> None:
        store = InMemorySubSessionStore()
        assert await store.remove("missing") is False

    async def test_list_sorted_by_created_at_desc(self) -> None:
        store = InMemorySubSessionStore()
        await store.add(
            SubSession(
                session_id="older",
                parent_pipeline_run_id="run-1",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        await store.add(
            SubSession(
                session_id="newer",
                parent_pipeline_run_id="run-1",
                created_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        result = await store.list_by_pipeline("run-1")
        assert result[0]["session_id"] == "newer"
        assert result[1]["session_id"] == "older"
