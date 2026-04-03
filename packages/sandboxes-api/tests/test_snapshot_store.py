"""Tests for InMemorySnapshotStore."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.types import SandboxSnapshot, SandboxSnapshotStatus
from lintel.sandboxes_api.snapshot_store import InMemorySnapshotStore


class TestInMemorySnapshotStore:
    async def test_add_and_get(self) -> None:
        store = InMemorySnapshotStore()
        snap = SandboxSnapshot(snapshot_id="s1", sandbox_id="sbx-1", project_id="p1")
        result = await store.add(snap)
        assert result["snapshot_id"] == "s1"
        assert result["sandbox_id"] == "sbx-1"

        got = await store.get("s1")
        assert got is not None
        assert got["snapshot_id"] == "s1"

    async def test_get_missing(self) -> None:
        store = InMemorySnapshotStore()
        assert await store.get("missing") is None

    async def test_list_all_empty(self) -> None:
        store = InMemorySnapshotStore()
        assert await store.list_all() == []

    async def test_list_all_with_filters(self) -> None:
        store = InMemorySnapshotStore()
        await store.add(
            SandboxSnapshot(
                snapshot_id="s1",
                sandbox_id="sbx-1",
                project_id="p1",
                pipeline_run_id="r1",
            ),
        )
        await store.add(
            SandboxSnapshot(
                snapshot_id="s2",
                sandbox_id="sbx-2",
                project_id="p2",
                pipeline_run_id="r2",
            ),
        )

        # Filter by project
        result = await store.list_all(project_id="p1")
        assert len(result) == 1
        assert result[0]["snapshot_id"] == "s1"

        # Filter by pipeline_run_id
        result = await store.list_all(pipeline_run_id="r2")
        assert len(result) == 1
        assert result[0]["snapshot_id"] == "s2"

        # Filter by sandbox_id
        result = await store.list_all(sandbox_id="sbx-1")
        assert len(result) == 1

        # Filter by status
        result = await store.list_all(status=SandboxSnapshotStatus.PENDING)
        assert len(result) == 2  # default status is PENDING

    async def test_update(self) -> None:
        store = InMemorySnapshotStore()
        await store.add(SandboxSnapshot(snapshot_id="s1", sandbox_id="sbx-1"))
        updated = await store.update("s1", {"status": "completed", "size_mb": 42})
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["size_mb"] == 42

    async def test_update_missing(self) -> None:
        store = InMemorySnapshotStore()
        assert await store.update("missing", {"status": "completed"}) is None

    async def test_remove(self) -> None:
        store = InMemorySnapshotStore()
        await store.add(SandboxSnapshot(snapshot_id="s1", sandbox_id="sbx-1"))
        assert await store.remove("s1") is True
        assert await store.get("s1") is None

    async def test_remove_missing(self) -> None:
        store = InMemorySnapshotStore()
        assert await store.remove("missing") is False

    async def test_list_sorted_by_created_at_desc(self) -> None:
        store = InMemorySnapshotStore()
        await store.add(
            SandboxSnapshot(
                snapshot_id="older",
                sandbox_id="sbx-1",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        await store.add(
            SandboxSnapshot(
                snapshot_id="newer",
                sandbox_id="sbx-2",
                created_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        result = await store.list_all()
        assert result[0]["snapshot_id"] == "newer"
        assert result[1]["snapshot_id"] == "older"
