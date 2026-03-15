"""Tests for vector store providers and factory."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lintel.memory.models import ScoredPoint
from lintel.memory.providers.base import VectorStoreProvider
from lintel.memory.providers.factory import VectorStoreFactory
from lintel.memory.providers.qdrant_provider import QdrantProvider

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_qdrant_client():
    client = AsyncMock()
    return client


@pytest.fixture
def provider(mock_qdrant_client):
    with patch(
        "lintel.memory.providers.qdrant_provider.AsyncQdrantClient",
        return_value=mock_qdrant_client,
    ):
        p = QdrantProvider(url="http://localhost:6333", api_key="test-key")
    p._client = mock_qdrant_client
    return p


# ── QdrantProvider ──────────────────────────────────────────────────


class TestQdrantProviderStoreEmbedding:
    async def test_calls_upsert(self, provider, mock_qdrant_client):
        await provider.store_embedding(
            collection="long_term_memory",
            id="emb-1",
            vector=[0.1, 0.2, 0.3],
            payload={"project_id": "p1"},
        )

        mock_qdrant_client.upsert.assert_awaited_once()
        call_kwargs = mock_qdrant_client.upsert.call_args
        assert call_kwargs.kwargs["collection_name"] == "long_term_memory"
        points = call_kwargs.kwargs["points"]
        assert len(points) == 1
        assert points[0].id == "emb-1"
        assert points[0].vector == [0.1, 0.2, 0.3]
        assert points[0].payload == {"project_id": "p1"}


class TestQdrantProviderSearch:
    async def test_returns_scored_points(self, provider, mock_qdrant_client):
        mock_point = SimpleNamespace(id="point-1", score=0.95, payload={"fact_id": "f1"})
        mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[mock_point])

        results = await provider.search(
            collection="episodic_memory",
            query_vector=[0.1, 0.2],
            top_k=3,
        )

        assert len(results) == 1
        assert isinstance(results[0], ScoredPoint)
        assert results[0].id == "point-1"
        assert results[0].score == 0.95
        assert results[0].payload == {"fact_id": "f1"}

    async def test_search_with_filters(self, provider, mock_qdrant_client):
        mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[])

        await provider.search(
            collection="long_term_memory",
            query_vector=[0.1],
            top_k=5,
            filters={"project_id": "p1"},
        )

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is not None

    async def test_search_without_filters(self, provider, mock_qdrant_client):
        mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[])

        await provider.search(
            collection="long_term_memory",
            query_vector=[0.1],
        )

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is None

    async def test_handles_none_score(self, provider, mock_qdrant_client):
        mock_point = SimpleNamespace(id="p1", score=None, payload={"k": "v"})
        mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[mock_point])

        results = await provider.search("col", [0.1])
        assert results[0].score == 0.0

    async def test_handles_none_payload(self, provider, mock_qdrant_client):
        mock_point = SimpleNamespace(id="p1", score=0.5, payload=None)
        mock_qdrant_client.query_points.return_value = SimpleNamespace(points=[mock_point])

        results = await provider.search("col", [0.1])
        assert results[0].payload == {}


class TestQdrantProviderDelete:
    async def test_calls_delete(self, provider, mock_qdrant_client):
        await provider.delete(collection="long_term_memory", id="emb-1")

        mock_qdrant_client.delete.assert_awaited_once()
        call_kwargs = mock_qdrant_client.delete.call_args.kwargs
        assert call_kwargs["collection_name"] == "long_term_memory"


class TestQdrantProviderCreateCollection:
    async def test_creates_with_correct_params(self, provider, mock_qdrant_client):
        await provider.create_collection(name="test_col", vector_size=768)

        mock_qdrant_client.create_collection.assert_awaited_once()
        call_kwargs = mock_qdrant_client.create_collection.call_args.kwargs
        assert call_kwargs["collection_name"] == "test_col"
        assert call_kwargs["vectors_config"].size == 768


class TestQdrantProviderEnsureCollection:
    async def test_handles_already_exists(self, provider, mock_qdrant_client):
        mock_qdrant_client.create_collection.side_effect = Exception("collection already exists")

        # Should not raise
        await provider.ensure_collection(name="existing_col", vector_size=1536)

    async def test_creates_new_collection(self, provider, mock_qdrant_client):
        mock_qdrant_client.create_collection.return_value = None

        await provider.ensure_collection(name="new_col", vector_size=1536)
        mock_qdrant_client.create_collection.assert_awaited_once()


class TestQdrantProviderHealthCheck:
    async def test_returns_true_when_healthy(self, provider, mock_qdrant_client):
        mock_qdrant_client.get_collections.return_value = []

        result = await provider.health_check()
        assert result is True

    async def test_returns_false_on_error(self, provider, mock_qdrant_client):
        mock_qdrant_client.get_collections.side_effect = Exception("connection refused")

        result = await provider.health_check()
        assert result is False


# ── VectorStoreFactory ──────────────────────────────────────────────


class TestVectorStoreFactory:
    def test_create_qdrant_provider(self):
        with patch("lintel.memory.providers.qdrant_provider.AsyncQdrantClient"):
            provider = VectorStoreFactory.create("qdrant", url="http://localhost:6333")
        assert isinstance(provider, QdrantProvider)
        assert isinstance(provider, VectorStoreProvider)

    def test_create_raises_for_unknown(self):
        with pytest.raises(ValueError, match="Unsupported vector store provider"):
            VectorStoreFactory.create("pinecone")

    def test_create_uses_kwargs(self):
        with patch("lintel.memory.providers.qdrant_provider.AsyncQdrantClient") as mock_cls:
            VectorStoreFactory.create("qdrant", url="http://custom:6333", api_key="my-key")
            mock_cls.assert_called_once_with(url="http://custom:6333", api_key="my-key")
