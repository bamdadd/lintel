"""Factory for creating vector store provider instances."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

from lintel.memory.providers.qdrant_provider import QdrantProvider

if TYPE_CHECKING:
    from lintel.memory.providers.base import VectorStoreProvider

log = structlog.get_logger(__name__)


class VectorStoreFactory:
    """Instantiate a :class:`VectorStoreProvider` by name."""

    @classmethod
    def create(cls, provider: str = "qdrant", **kwargs: str) -> VectorStoreProvider:
        """Return a configured provider instance.

        Parameters are read from *kwargs* first, falling back to environment
        variables when a value is not supplied explicitly.
        """
        provider = provider or os.environ.get("LINTEL_VECTOR_STORE_PROVIDER", "qdrant")

        if provider == "qdrant":
            url = kwargs.get("url") or os.environ.get("LINTEL_QDRANT_URL", "http://localhost:6333")
            api_key = kwargs.get("api_key") or os.environ.get("LINTEL_QDRANT_API_KEY")
            log.info("vector_store_created", provider=provider, url=url)
            return QdrantProvider(url=url, api_key=api_key)

        # Future providers ------------------------------------------------
        # elif provider == "weaviate":
        #     ...
        # elif provider == "pinecone":
        #     ...

        raise ValueError(f"Unsupported vector store provider: {provider!r}. Supported: 'qdrant'.")
