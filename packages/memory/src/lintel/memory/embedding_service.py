"""Embedding generation service using raw HTTP calls (no openai SDK)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

_DEFAULT_OPENAI_URL = "https://api.openai.com/v1"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"


class EmbeddingService:
    """Generate text embeddings via OpenAI or Ollama APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._provider = provider
        self._model = model
        self._base_url = base_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for *text*."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for every entry in *texts*."""
        if self._provider == "openai":
            return await self._embed_openai(texts)
        if self._provider == "ollama":
            return await self._embed_ollama(texts)
        raise ValueError(f"Unsupported embedding provider: {self._provider!r}")

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> EmbeddingService:
        """Build an :class:`EmbeddingService` from environment variables."""
        provider = os.environ.get("LINTEL_EMBEDDING_PROVIDER", "openai")
        model = os.environ.get("LINTEL_EMBEDDING_MODEL", "text-embedding-3-small")
        api_key = os.environ.get("OPENAI_API_KEY")

        base_url: str | None = None
        if provider == "ollama":
            base_url = os.environ.get("LINTEL_MODEL_OLLAMA_API_BASE", _DEFAULT_OLLAMA_URL)

        return cls(
            api_key=api_key,
            provider=provider,
            model=model,
            base_url=base_url,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._base_url or _DEFAULT_OPENAI_URL}/embeddings"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload: dict[str, Any] = {
            "input": texts,
            "model": self._model,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # OpenAI returns {"data": [{"embedding": [...], "index": 0}, ...]}
        sorted_items = sorted(data["data"], key=lambda d: d["index"])
        return [item["embedding"] for item in sorted_items]

    async def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        base = self._base_url or _DEFAULT_OLLAMA_URL
        url = f"{base}/api/embeddings"

        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for text in texts:
                payload: dict[str, Any] = {
                    "model": self._model,
                    "prompt": text,
                }
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                embeddings.append(data["embedding"])

        return embeddings
