"""Tests for InMemoryTechSpecStore."""

from lintel.domain.types import TechSpec, TechSpecStatus
from lintel.tech_spec_api.store import InMemoryTechSpecStore


class TestInMemoryTechSpecStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryTechSpecStore()
        spec = TechSpec(id="ts-1", project_id="p1", title="Spec 1")
        await store.add(spec)
        result = await store.get("ts-1")
        assert result is not None
        assert result.title == "Spec 1"

    async def test_get_returns_none_when_not_found(self) -> None:
        store = InMemoryTechSpecStore()
        result = await store.get("nonexistent")
        assert result is None

    async def test_list_all(self) -> None:
        store = InMemoryTechSpecStore()
        await store.add(TechSpec(id="ts-1", project_id="p1", title="A"))
        await store.add(TechSpec(id="ts-2", project_id="p2", title="B"))
        result = await store.list_all()
        assert len(result) == 2

    async def test_list_all_filter_by_project(self) -> None:
        store = InMemoryTechSpecStore()
        await store.add(TechSpec(id="ts-1", project_id="p1", title="A"))
        await store.add(TechSpec(id="ts-2", project_id="p2", title="B"))
        result = await store.list_all(project_id="p1")
        assert len(result) == 1
        assert result[0].id == "ts-1"

    async def test_update(self) -> None:
        store = InMemoryTechSpecStore()
        spec = TechSpec(id="ts-1", project_id="p1", title="Old")
        await store.add(spec)
        updated = TechSpec(id="ts-1", project_id="p1", title="New", status=TechSpecStatus.REVIEW)
        await store.update(updated)
        result = await store.get("ts-1")
        assert result is not None
        assert result.title == "New"
        assert result.status == TechSpecStatus.REVIEW

    async def test_remove(self) -> None:
        store = InMemoryTechSpecStore()
        await store.add(TechSpec(id="ts-1", project_id="p1", title="A"))
        await store.remove("ts-1")
        assert await store.get("ts-1") is None
