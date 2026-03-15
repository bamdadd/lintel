"""Abstract base class for vector store providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.memory.models import ScoredPoint

log = structlog.get_logger(__name__)


class VectorStoreProvider(ABC):
    """Interface that all vector store backends must implement."""

    @abstractmethod
    async def store_embedding(
        self,
        collection: str,
        embedding_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Upsert a single embedding into the given collection."""

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredPoint]:
        """Return the *top_k* nearest neighbours for *query_vector*."""

    @abstractmethod
    async def delete(self, collection: str, embedding_id: str) -> None:
        """Remove a point by id from *collection*."""

    @abstractmethod
    async def create_collection(self, name: str, vector_size: int) -> None:
        """Create a new collection with the specified vector dimensionality."""

    async def ensure_collection(self, name: str, vector_size: int) -> None:
        """Create *name* if it does not already exist.

        Swallows errors raised when the collection is already present.
        """
        try:
            await self.create_collection(name, vector_size)
            log.info("collection_created", name=name, vector_size=vector_size)
        except Exception:
            log.debug("collection_already_exists", name=name)

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the backend is reachable."""
