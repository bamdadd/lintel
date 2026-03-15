"""Tests for lintel.memory.embedding_service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lintel.memory.embedding_service import EmbeddingService

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def openai_service():
    return EmbeddingService(
        api_key="sk-test-key",
        provider="openai",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
    )


@pytest.fixture
def ollama_service():
    return EmbeddingService(
        provider="ollama",
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )


def _mock_openai_response(embeddings: list[list[float]]):
    """Build a mock httpx.Response matching OpenAI's embedding response shape."""
    data = [{"embedding": emb, "index": idx} for idx, emb in enumerate(embeddings)]
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": data}
    return resp


def _mock_ollama_response(embedding: list[float]):
    """Build a mock httpx.Response matching Ollama's embedding response shape."""
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"embedding": embedding}
    return resp


# ── OpenAI Provider ─────────────────────────────────────────────────


class TestEmbedOpenAI:
    async def test_embed_returns_vector(self, openai_service):
        expected = [0.1, 0.2, 0.3]
        mock_response = _mock_openai_response([expected])

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            result = await openai_service.embed("hello world")

        assert result == expected
        mock_client.post.assert_awaited_once()
        call_kwargs = mock_client.post.call_args
        assert "embeddings" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"]["input"] == ["hello world"]
        assert call_kwargs.kwargs["json"]["model"] == "text-embedding-3-small"

    async def test_embed_batch_returns_multiple_vectors(self, openai_service):
        expected = [[0.1, 0.2], [0.3, 0.4]]
        mock_response = _mock_openai_response(expected)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            result = await openai_service.embed_batch(["a", "b"])

        assert result == expected

    async def test_embed_sets_auth_header(self, openai_service):
        mock_response = _mock_openai_response([[0.1]])

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            await openai_service.embed("test")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-test-key"

    async def test_embed_sorts_by_index(self, openai_service):
        """OpenAI may return items out of order; they must be sorted by index."""
        data = [
            {"embedding": [0.9, 0.8], "index": 1},
            {"embedding": [0.1, 0.2], "index": 0},
        ]
        resp = MagicMock(spec=httpx.Response)
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": data}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            result = await openai_service.embed_batch(["first", "second"])

        assert result == [[0.1, 0.2], [0.9, 0.8]]


# ── Ollama Provider ─────────────────────────────────────────────────


class TestEmbedOllama:
    async def test_embed_returns_vector(self, ollama_service):
        expected = [0.5, 0.6, 0.7]

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _mock_ollama_response(expected)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            result = await ollama_service.embed("hello")

        assert result == expected

    async def test_embed_batch_calls_per_text(self, ollama_service):
        vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [_mock_ollama_response(v) for v in vectors]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            result = await ollama_service.embed_batch(["a", "b", "c"])

        assert result == vectors
        assert mock_client.post.await_count == 3

    async def test_embed_uses_correct_url(self, ollama_service):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _mock_ollama_response([0.1])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            await ollama_service.embed("test")

        url = mock_client.post.call_args.args[0]
        assert url == "http://localhost:11434/api/embeddings"


# ── Error Handling ──────────────────────────────────────────────────


class TestErrorHandling:
    async def test_openai_http_error_propagates(self, openai_service):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await openai_service.embed("test")

    async def test_unsupported_provider_raises(self):
        service = EmbeddingService(provider="unknown_provider")
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            await service.embed_batch(["test"])

    async def test_ollama_http_error_propagates(self, ollama_service):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lintel.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await ollama_service.embed("test")


# ── from_env ────────────────────────────────────────────────────────


class TestFromEnv:
    def test_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            svc = EmbeddingService.from_env()
        assert svc._provider == "openai"
        assert svc._model == "text-embedding-3-small"
        assert svc._api_key is None
        assert svc._base_url is None

    def test_reads_env_vars_openai(self):
        env = {
            "LINTEL_EMBEDDING_PROVIDER": "openai",
            "LINTEL_EMBEDDING_MODEL": "text-embedding-ada-002",
            "OPENAI_API_KEY": "sk-envkey",
        }
        with patch.dict("os.environ", env, clear=True):
            svc = EmbeddingService.from_env()
        assert svc._provider == "openai"
        assert svc._model == "text-embedding-ada-002"
        assert svc._api_key == "sk-envkey"
        assert svc._base_url is None

    def test_reads_env_vars_ollama(self):
        env = {
            "LINTEL_EMBEDDING_PROVIDER": "ollama",
            "LINTEL_EMBEDDING_MODEL": "nomic-embed-text",
            "LINTEL_MODEL_OLLAMA_API_BASE": "http://ollama:11434",
        }
        with patch.dict("os.environ", env, clear=True):
            svc = EmbeddingService.from_env()
        assert svc._provider == "ollama"
        assert svc._model == "nomic-embed-text"
        assert svc._base_url == "http://ollama:11434"

    def test_ollama_default_base_url(self):
        env = {"LINTEL_EMBEDDING_PROVIDER": "ollama"}
        with patch.dict("os.environ", env, clear=True):
            svc = EmbeddingService.from_env()
        assert svc._base_url == "http://localhost:11434"
