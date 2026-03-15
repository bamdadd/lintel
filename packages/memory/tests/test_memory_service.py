"""Tests for lintel.memory.memory_service.MemoryService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from lintel.memory.memory_service import MemoryService
from lintel.memory.models import MemoryFact, MemoryType, ScoredPoint

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda fact: fact)
    repo.get = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    repo.update = AsyncMock(side_effect=lambda fact: fact)
    return repo


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    vs = AsyncMock()
    vs.store_embedding = AsyncMock()
    vs.search = AsyncMock(return_value=[])
    vs.delete = AsyncMock()
    vs.ensure_collection = AsyncMock()
    return vs


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    es = AsyncMock()
    es.embed = AsyncMock(return_value=[0.1] * 1536)
    return es


@pytest.fixture
def service(
    mock_repository: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_embedding_service: AsyncMock,
) -> MemoryService:
    return MemoryService(
        repository=mock_repository,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
    )


def _make_fact(
    project_id: UUID | None = None,
    memory_type: MemoryType = MemoryType.LONG_TERM,
    fact_type: str = "test_fact",
    content: str = "test content",
    embedding_id: str | None = "emb-1",
    source_workflow_id: UUID | None = None,
) -> MemoryFact:
    return MemoryFact(
        project_id=project_id or uuid4(),
        memory_type=memory_type,
        fact_type=fact_type,
        content=content,
        embedding_id=embedding_id,
        source_workflow_id=source_workflow_id,
    )


# ── store_memory ────────────────────────────────────────────────────


class TestStoreMemory:
    async def test_generates_embedding_stores_and_saves(
        self,
        service: MemoryService,
        mock_embedding_service: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_repository: AsyncMock,
    ) -> None:
        project_id = uuid4()
        result = await service.store_memory(
            project_id=project_id,
            content="The sky is blue",
            memory_type=MemoryType.LONG_TERM,
            fact_type="observation",
        )

        # Embedding generated
        mock_embedding_service.embed.assert_awaited_once_with("The sky is blue")

        # Stored in Qdrant
        mock_vector_store.store_embedding.assert_awaited_once()
        vs_call = mock_vector_store.store_embedding.call_args
        assert vs_call.kwargs["collection"] == "long_term_memory"
        assert vs_call.kwargs["vector"] == [0.1] * 1536
        assert vs_call.kwargs["payload"]["project_id"] == str(project_id)
        assert vs_call.kwargs["payload"]["memory_type"] == "long_term"

        # Saved to Postgres
        mock_repository.save.assert_awaited_once()

        # Returned fact
        assert isinstance(result, MemoryFact)
        assert result.content == "The sky is blue"
        assert result.memory_type == MemoryType.LONG_TERM

    async def test_stores_episodic_in_correct_collection(
        self, service: MemoryService, mock_vector_store: AsyncMock
    ) -> None:
        await service.store_memory(
            project_id=uuid4(),
            content="workflow done",
            memory_type=MemoryType.EPISODIC,
            fact_type="workflow_summary",
        )

        vs_call = mock_vector_store.store_embedding.call_args
        assert vs_call.kwargs["collection"] == "episodic_memory"

    async def test_passes_source_workflow_id(
        self, service: MemoryService, mock_repository: AsyncMock
    ) -> None:
        wf_id = uuid4()
        result = await service.store_memory(
            project_id=uuid4(),
            content="test",
            memory_type=MemoryType.LONG_TERM,
            fact_type="test",
            source_workflow_id=wf_id,
        )
        assert result.source_workflow_id == wf_id


# ── recall ──────────────────────────────────────────────────────────


class TestRecall:
    async def test_with_specific_memory_type(
        self,
        service: MemoryService,
        mock_vector_store: AsyncMock,
        mock_repository: AsyncMock,
        mock_embedding_service: AsyncMock,
    ) -> None:
        project_id = uuid4()
        fact = _make_fact(project_id=project_id)

        mock_vector_store.search.return_value = [
            ScoredPoint(
                id="emb-1",
                score=0.9,
                payload={"fact_id": str(fact.id), "project_id": str(project_id)},
            )
        ]
        mock_repository.get.return_value = fact

        chunks = await service.recall(
            project_id=project_id,
            query="find facts",
            memory_type=MemoryType.LONG_TERM,
            top_k=5,
        )

        # Should search only long_term_memory
        mock_vector_store.search.assert_awaited_once()
        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["collection"] == "long_term_memory"

        assert len(chunks) == 1
        assert chunks[0].fact.id == fact.id
        assert chunks[0].rank == 1

    async def test_with_none_memory_type_searches_all(
        self,
        service: MemoryService,
        mock_vector_store: AsyncMock,
        mock_embedding_service: AsyncMock,
    ) -> None:
        project_id = uuid4()

        mock_vector_store.search.return_value = []

        await service.recall(
            project_id=project_id,
            query="find anything",
            memory_type=None,
        )

        # Should search all COLLECTIONS
        assert mock_vector_store.search.await_count == len(MemoryService.COLLECTIONS)

    async def test_returns_empty_list_when_no_results(
        self, service: MemoryService, mock_vector_store: AsyncMock
    ) -> None:
        mock_vector_store.search.return_value = []

        chunks = await service.recall(
            project_id=uuid4(),
            query="nothing here",
            memory_type=MemoryType.LONG_TERM,
        )

        assert chunks == []

    async def test_ranks_by_descending_score(
        self, service: MemoryService, mock_vector_store: AsyncMock, mock_repository: AsyncMock
    ) -> None:
        project_id = uuid4()
        fact1 = _make_fact(project_id=project_id, content="low score")
        fact2 = _make_fact(project_id=project_id, content="high score")

        mock_vector_store.search.return_value = [
            ScoredPoint(
                id="emb-low",
                score=0.5,
                payload={"fact_id": str(fact1.id)},
            ),
            ScoredPoint(
                id="emb-high",
                score=0.95,
                payload={"fact_id": str(fact2.id)},
            ),
        ]
        mock_repository.get.side_effect = [fact1, fact2]

        chunks = await service.recall(
            project_id=project_id,
            query="test",
            memory_type=MemoryType.LONG_TERM,
        )

        assert len(chunks) == 2
        assert chunks[0].score == 0.95
        assert chunks[0].rank == 1
        assert chunks[1].score == 0.5
        assert chunks[1].rank == 2

    async def test_skips_points_without_fact_id(
        self, service: MemoryService, mock_vector_store: AsyncMock, mock_repository: AsyncMock
    ) -> None:
        mock_vector_store.search.return_value = [
            ScoredPoint(id="emb-1", score=0.9, payload={}),  # no fact_id
        ]

        chunks = await service.recall(
            project_id=uuid4(),
            query="test",
            memory_type=MemoryType.LONG_TERM,
        )
        assert chunks == []
        mock_repository.get.assert_not_awaited()

    async def test_skips_missing_facts(
        self, service: MemoryService, mock_vector_store: AsyncMock, mock_repository: AsyncMock
    ) -> None:
        mock_vector_store.search.return_value = [
            ScoredPoint(
                id="emb-1",
                score=0.9,
                payload={"fact_id": str(uuid4())},
            ),
        ]
        mock_repository.get.return_value = None

        chunks = await service.recall(
            project_id=uuid4(),
            query="test",
            memory_type=MemoryType.LONG_TERM,
        )
        assert chunks == []


# ── consolidate_from_workflow ───────────────────────────────────────


class TestConsolidateFromWorkflow:
    async def test_stores_new_memory_when_no_duplicate(
        self,
        service: MemoryService,
        mock_vector_store: AsyncMock,
        mock_repository: AsyncMock,
        mock_embedding_service: AsyncMock,
    ) -> None:
        project_id = uuid4()
        workflow_id = uuid4()

        mock_vector_store.search.return_value = []

        results = await service.consolidate_from_workflow(
            workflow_id=workflow_id,
            project_id=project_id,
            summary_text="New workflow summary",
        )

        assert len(results) == 1
        assert results[0].content == "New workflow summary"
        assert results[0].memory_type == MemoryType.EPISODIC
        mock_repository.save.assert_awaited_once()

    async def test_deduplicates_high_similarity(
        self,
        service: MemoryService,
        mock_vector_store: AsyncMock,
        mock_repository: AsyncMock,
        mock_embedding_service: AsyncMock,
    ) -> None:
        project_id = uuid4()
        workflow_id = uuid4()
        existing_fact = _make_fact(
            project_id=project_id,
            memory_type=MemoryType.EPISODIC,
            content="Old summary",
            embedding_id="old-emb",
        )

        # Return high-similarity match
        mock_vector_store.search.return_value = [
            ScoredPoint(
                id="old-emb",
                score=0.98,  # > 0.95 threshold
                payload={"fact_id": str(existing_fact.id)},
            )
        ]
        mock_repository.get.return_value = existing_fact

        results = await service.consolidate_from_workflow(
            workflow_id=workflow_id,
            project_id=project_id,
            summary_text="Updated summary",
        )

        # Should update existing rather than create new
        assert len(results) == 1
        mock_repository.update.assert_awaited_once()
        mock_repository.save.assert_not_awaited()

        updated_fact = mock_repository.update.call_args.args[0]
        assert updated_fact.content == "Updated summary"
        assert updated_fact.source_workflow_id == workflow_id

    async def test_stores_new_when_similarity_below_threshold(
        self, service: MemoryService, mock_vector_store: AsyncMock, mock_repository: AsyncMock
    ) -> None:
        project_id = uuid4()

        mock_vector_store.search.return_value = [
            ScoredPoint(
                id="some-emb",
                score=0.80,  # < 0.95 threshold
                payload={"fact_id": str(uuid4())},
            )
        ]

        results = await service.consolidate_from_workflow(
            workflow_id=uuid4(),
            project_id=project_id,
            summary_text="Different enough summary",
        )

        assert len(results) == 1
        mock_repository.save.assert_awaited_once()
        mock_repository.update.assert_not_awaited()


# ── delete_memory ───────────────────────────────────────────────────


class TestDeleteMemory:
    async def test_removes_from_both_stores(
        self, service: MemoryService, mock_repository: AsyncMock, mock_vector_store: AsyncMock
    ) -> None:
        memory_id = uuid4()
        fact = _make_fact(
            memory_type=MemoryType.LONG_TERM,
            embedding_id="emb-to-delete",
        )
        fact.id = memory_id
        mock_repository.get.return_value = fact

        result = await service.delete_memory(memory_id)

        assert result is True
        mock_vector_store.delete.assert_awaited_once_with("long_term_memory", "emb-to-delete")
        mock_repository.delete.assert_awaited_once_with(memory_id)

    async def test_returns_false_for_nonexistent(
        self, service: MemoryService, mock_repository: AsyncMock, mock_vector_store: AsyncMock
    ) -> None:
        mock_repository.get.return_value = None

        result = await service.delete_memory(uuid4())

        assert result is False
        mock_vector_store.delete.assert_not_awaited()
        mock_repository.delete.assert_not_awaited()

    async def test_skips_vector_delete_without_embedding_id(
        self, service: MemoryService, mock_repository: AsyncMock, mock_vector_store: AsyncMock
    ) -> None:
        memory_id = uuid4()
        fact = _make_fact(memory_type=MemoryType.EPISODIC, embedding_id=None)
        # Override the default embedding_id from _make_fact
        fact.embedding_id = None
        fact.id = memory_id
        mock_repository.get.return_value = fact

        result = await service.delete_memory(memory_id)

        assert result is True
        mock_vector_store.delete.assert_not_awaited()
        mock_repository.delete.assert_awaited_once_with(memory_id)


# ── initialize ──────────────────────────────────────────────────────


class TestInitialize:
    async def test_creates_all_collections(
        self, service: MemoryService, mock_vector_store: AsyncMock
    ) -> None:
        await service.initialize()

        assert mock_vector_store.ensure_collection.await_count == len(MemoryService.COLLECTIONS)

        called_names = [
            call.kwargs["name"] if "name" in call.kwargs else call.args[0]
            for call in mock_vector_store.ensure_collection.call_args_list
        ]
        for collection in MemoryService.COLLECTIONS:
            assert collection in called_names

    async def test_uses_correct_vector_size(
        self, service: MemoryService, mock_vector_store: AsyncMock
    ) -> None:
        await service.initialize()

        for call in mock_vector_store.ensure_collection.call_args_list:
            vector_size = call.kwargs.get("vector_size") or call.args[1]
            assert vector_size == MemoryService.VECTOR_SIZE
