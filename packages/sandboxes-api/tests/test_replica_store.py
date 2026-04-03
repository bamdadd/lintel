"""Tests for the in-memory replica config store."""

from lintel.sandboxes_api.replica_store import DatabaseReplicaConfig, InMemoryReplicaConfigStore


class TestInMemoryReplicaConfigStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryReplicaConfigStore()
        replica = DatabaseReplicaConfig(
            replica_id="r1",
            project_id="proj1",
            name="staging",
            host="staging.db",
        )
        await store.add(replica)
        result = await store.get("r1")
        assert result is not None
        assert result.name == "staging"

    async def test_get_returns_none_for_missing(self) -> None:
        store = InMemoryReplicaConfigStore()
        assert await store.get("missing") is None

    async def test_list_for_project(self) -> None:
        store = InMemoryReplicaConfigStore()
        await store.add(
            DatabaseReplicaConfig(replica_id="r1", project_id="proj1", name="a", host="a.db")
        )
        await store.add(
            DatabaseReplicaConfig(replica_id="r2", project_id="proj2", name="b", host="b.db")
        )
        await store.add(
            DatabaseReplicaConfig(replica_id="r3", project_id="proj1", name="c", host="c.db")
        )
        result = await store.list_for_project("proj1")
        assert len(result) == 2
        assert {r.replica_id for r in result} == {"r1", "r3"}

    async def test_list_all(self) -> None:
        store = InMemoryReplicaConfigStore()
        await store.add(
            DatabaseReplicaConfig(replica_id="r1", project_id="p1", name="a", host="a.db")
        )
        await store.add(
            DatabaseReplicaConfig(replica_id="r2", project_id="p2", name="b", host="b.db")
        )
        assert len(await store.list_all()) == 2

    async def test_update(self) -> None:
        store = InMemoryReplicaConfigStore()
        replica = DatabaseReplicaConfig(replica_id="r1", project_id="p1", name="old", host="old.db")
        await store.add(replica)
        updated = DatabaseReplicaConfig(replica_id="r1", project_id="p1", name="new", host="new.db")
        await store.update(updated)
        result = await store.get("r1")
        assert result is not None
        assert result.name == "new"
        assert result.host == "new.db"

    async def test_remove(self) -> None:
        store = InMemoryReplicaConfigStore()
        await store.add(
            DatabaseReplicaConfig(replica_id="r1", project_id="p1", name="a", host="a.db")
        )
        await store.remove("r1")
        assert await store.get("r1") is None

    async def test_remove_missing_is_silent(self) -> None:
        store = InMemoryReplicaConfigStore()
        await store.remove("missing")  # Should not raise
