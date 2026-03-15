"""Tests for the memory API router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lintel.memory.models import MemoryChunk, MemoryFact, MemoryType

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient


_PROJECT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_fact(
    *,
    fact_id: UUID | None = None,
    project_id: UUID = _PROJECT_ID,
    content: str = "Test memory content",
    memory_type: MemoryType = MemoryType.LONG_TERM,
    fact_type: str = "pattern",
) -> MemoryFact:
    return MemoryFact(
        id=fact_id or uuid4(),
        project_id=project_id,
        memory_type=memory_type,
        fact_type=fact_type,
        content=content,
        embedding_id="emb-123",
        source_workflow_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_chunk(
    *,
    fact: MemoryFact | None = None,
    score: float = 0.92,
    rank: int = 1,
) -> MemoryChunk:
    return MemoryChunk(
        fact=fact or _make_fact(),
        score=score,
        rank=rank,
    )


class TestListMemories:
    def test_returns_paginated_list(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        fact = _make_fact()
        mock_memory_service.list_memories.return_value = ([fact], 1)

        resp = client.get("/api/v1/memory", params={"project_id": str(_PROJECT_ID)})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Test memory content"

    def test_with_memory_type_filter(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        mock_memory_service.list_memories.return_value = ([], 0)

        resp = client.get(
            "/api/v1/memory",
            params={"project_id": str(_PROJECT_ID), "memory_type": "episodic"},
        )

        assert resp.status_code == 200
        mock_memory_service.list_memories.assert_awaited_once_with(
            project_id=_PROJECT_ID,
            memory_type="episodic",
            page=1,
            page_size=20,
        )

    def test_with_pagination_params(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        mock_memory_service.list_memories.return_value = ([], 0)

        resp = client.get(
            "/api/v1/memory",
            params={"project_id": str(_PROJECT_ID), "page": 3, "page_size": 10},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 3
        assert data["page_size"] == 10
        mock_memory_service.list_memories.assert_awaited_once_with(
            project_id=_PROJECT_ID,
            memory_type=None,
            page=3,
            page_size=10,
        )

    def test_missing_project_id_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory")
        assert resp.status_code == 422


class TestSearchMemories:
    def test_returns_search_results(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        fact = _make_fact()
        # search() returns MemoryChunk-like objects; the route uses model_validate
        # with from_attributes=True so we provide objects with matching attributes.
        chunk = _make_chunk(fact=fact)
        # The route maps chunk attributes to MemoryChunkResponse.
        # We need an object whose attributes match MemoryChunkResponse fields.
        chunk_obj = type(
            "ChunkResult",
            (),
            {
                "id": fact.id,
                "project_id": fact.project_id,
                "memory_type": fact.memory_type,
                "fact_type": fact.fact_type,
                "content": fact.content,
                "score": chunk.score,
                "rank": chunk.rank,
                "source_workflow_id": fact.source_workflow_id,
                "created_at": fact.created_at,
            },
        )()
        mock_memory_service.search.return_value = [chunk_obj]

        resp = client.get(
            "/api/v1/memory/search",
            params={"q": "test query", "project_id": str(_PROJECT_ID)},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "Test memory content"
        assert data["results"][0]["score"] == 0.92

    def test_with_filters(self, client: TestClient, mock_memory_service: AsyncMock) -> None:
        mock_memory_service.search.return_value = []

        resp = client.get(
            "/api/v1/memory/search",
            params={
                "q": "query",
                "project_id": str(_PROJECT_ID),
                "memory_type": "long_term",
                "top_k": 10,
            },
        )

        assert resp.status_code == 200
        mock_memory_service.search.assert_awaited_once_with(
            query="query",
            project_id=_PROJECT_ID,
            memory_type="long_term",
            top_k=10,
        )

    def test_missing_query_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/memory/search",
            params={"project_id": str(_PROJECT_ID)},
        )
        assert resp.status_code == 422


class TestGetMemory:
    def test_returns_single_fact(self, client: TestClient, mock_memory_service: AsyncMock) -> None:
        fact = _make_fact()
        mock_memory_service.get_memory.return_value = fact

        resp = client.get(f"/api/v1/memory/{fact.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(fact.id)
        assert data["content"] == "Test memory content"
        assert data["memory_type"] == "long_term"

    def test_returns_404_for_missing(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        missing_id = uuid4()
        mock_memory_service.get_memory.return_value = None

        resp = client.get(f"/api/v1/memory/{missing_id}")

        assert resp.status_code == 404
        assert str(missing_id) in resp.json()["detail"]


class TestCreateMemory:
    def test_creates_memory_returns_201(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        fact = _make_fact()
        mock_memory_service.create_memory.return_value = fact

        resp = client.post(
            "/api/v1/memory",
            json={
                "project_id": str(_PROJECT_ID),
                "content": "Test memory content",
                "memory_type": "long_term",
                "fact_type": "pattern",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Test memory content"
        assert data["fact_type"] == "pattern"
        mock_memory_service.create_memory.assert_awaited_once_with(
            project_id=_PROJECT_ID,
            content="Test memory content",
            memory_type="long_term",
            fact_type="pattern",
            source_workflow_id=None,
        )

    def test_validates_required_fields_returns_422(
        self,
        client: TestClient,
    ) -> None:
        # Missing required 'content' and 'memory_type' and 'fact_type'
        resp = client.post(
            "/api/v1/memory",
            json={"project_id": str(_PROJECT_ID)},
        )
        assert resp.status_code == 422

    def test_validates_project_id_format(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={
                "project_id": "not-a-uuid",
                "content": "test",
                "memory_type": "long_term",
                "fact_type": "pattern",
            },
        )
        assert resp.status_code == 422

    def test_with_source_workflow_id(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        workflow_id = uuid4()
        fact = _make_fact()
        fact.source_workflow_id = workflow_id
        mock_memory_service.create_memory.return_value = fact

        resp = client.post(
            "/api/v1/memory",
            json={
                "project_id": str(_PROJECT_ID),
                "content": "learned from workflow",
                "memory_type": "episodic",
                "fact_type": "convention",
                "source_workflow_id": str(workflow_id),
            },
        )

        assert resp.status_code == 201
        assert resp.json()["source_workflow_id"] == str(workflow_id)


class TestDeleteMemory:
    def test_returns_204_on_success(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        memory_id = uuid4()
        mock_memory_service.delete_memory.return_value = True

        resp = client.delete(f"/api/v1/memory/{memory_id}")

        assert resp.status_code == 204
        mock_memory_service.delete_memory.assert_awaited_once_with(memory_id=memory_id)

    def test_returns_404_for_missing(
        self, client: TestClient, mock_memory_service: AsyncMock
    ) -> None:
        missing_id = uuid4()
        mock_memory_service.delete_memory.return_value = False

        resp = client.delete(f"/api/v1/memory/{missing_id}")

        assert resp.status_code == 404
        assert str(missing_id) in resp.json()["detail"]
