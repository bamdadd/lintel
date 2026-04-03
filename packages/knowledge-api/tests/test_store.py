"""Tests for InMemoryKnowledgeStore."""

from lintel.knowledge_api.store import InMemoryKnowledgeStore
from lintel.knowledge_api.types import KnowledgeEntry, SourceType


class TestInMemoryKnowledgeStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryKnowledgeStore()
        entry = KnowledgeEntry(id="k-1", project_id="p-1", title="Design doc")
        await store.add(entry)
        result = await store.get("k-1")
        assert result is not None
        assert result.title == "Design doc"

    async def test_get_returns_none_when_missing(self) -> None:
        store = InMemoryKnowledgeStore()
        assert await store.get("missing") is None

    async def test_list_all(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(KnowledgeEntry(id="k-1", project_id="p-1", title="A"))
        await store.add(KnowledgeEntry(id="k-2", project_id="p-2", title="B"))
        entries = await store.list_all()
        assert len(entries) == 2

    async def test_list_all_filters_by_project(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(KnowledgeEntry(id="k-1", project_id="p-1", title="A"))
        await store.add(KnowledgeEntry(id="k-2", project_id="p-2", title="B"))
        entries = await store.list_all(project_id="p-1")
        assert len(entries) == 1
        assert entries[0].id == "k-1"

    async def test_update(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(KnowledgeEntry(id="k-1", project_id="p-1", title="Old"))
        updated = KnowledgeEntry(id="k-1", project_id="p-1", title="New")
        await store.update(updated)
        result = await store.get("k-1")
        assert result is not None
        assert result.title == "New"

    async def test_remove(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(KnowledgeEntry(id="k-1", project_id="p-1", title="A"))
        await store.remove("k-1")
        assert await store.get("k-1") is None

    async def test_remove_missing_is_noop(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.remove("missing")  # should not raise


class TestSearch:
    async def test_search_by_embedding(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(
            KnowledgeEntry(
                id="k-1",
                project_id="p-1",
                title="A",
                embedding=(1.0, 0.0, 0.0),
            )
        )
        await store.add(
            KnowledgeEntry(
                id="k-2",
                project_id="p-1",
                title="B",
                embedding=(0.0, 1.0, 0.0),
            )
        )
        results = await store.search((1.0, 0.0, 0.0))
        assert len(results) == 2
        assert results[0][0].id == "k-1"
        assert results[0][1] > results[1][1]

    async def test_search_skips_entries_without_embedding(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(KnowledgeEntry(id="k-1", project_id="p-1", title="No vec"))
        await store.add(
            KnowledgeEntry(
                id="k-2",
                project_id="p-1",
                title="Has vec",
                embedding=(1.0, 0.0),
            )
        )
        results = await store.search((1.0, 0.0))
        assert len(results) == 1
        assert results[0][0].id == "k-2"

    async def test_search_filters_by_project(self) -> None:
        store = InMemoryKnowledgeStore()
        await store.add(
            KnowledgeEntry(
                id="k-1",
                project_id="p-1",
                title="A",
                embedding=(1.0, 0.0),
            )
        )
        await store.add(
            KnowledgeEntry(
                id="k-2",
                project_id="p-2",
                title="B",
                embedding=(1.0, 0.0),
            )
        )
        results = await store.search((1.0, 0.0), project_id="p-1")
        assert len(results) == 1
        assert results[0][0].id == "k-1"

    async def test_search_respects_limit(self) -> None:
        store = InMemoryKnowledgeStore()
        for i in range(5):
            await store.add(
                KnowledgeEntry(
                    id=f"k-{i}",
                    project_id="p-1",
                    title=f"Entry {i}",
                    source_type=SourceType.DOCUMENT,
                    embedding=(1.0, 0.0),
                )
            )
        results = await store.search((1.0, 0.0), limit=2)
        assert len(results) == 2
