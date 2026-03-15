"""Qdrant implementation of :class:`VectorStoreProvider`."""

from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)
import structlog

from lintel.memory.models import ScoredPoint
from lintel.memory.providers.base import VectorStoreProvider

log = structlog.get_logger(__name__)


class QdrantProvider(VectorStoreProvider):
    """Vector store backed by Qdrant."""

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._api_key = api_key
        self._client = AsyncQdrantClient(url=url, api_key=api_key)

    # ------------------------------------------------------------------
    # VectorStoreProvider interface
    # ------------------------------------------------------------------

    async def store_embedding(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        await self._client.upsert(
            collection_name=collection,
            points=[
                PointStruct(id=id, vector=vector, payload=payload),
            ],
        )
        log.debug("embedding_stored", collection=collection, id=id)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[ScoredPoint]:
        qdrant_filter: Filter | None = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        scored: list[ScoredPoint] = []
        for point in results.points:
            scored.append(
                ScoredPoint(
                    id=str(point.id),
                    score=point.score if point.score is not None else 0.0,
                    payload=point.payload or {},
                )
            )
        return scored

    async def delete(self, collection: str, id: str) -> None:
        await self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[id]),
        )
        log.debug("point_deleted", collection=collection, id=id)

    async def create_collection(self, name: str, vector_size: int) -> None:
        await self._client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        log.info("qdrant_collection_created", name=name, vector_size=vector_size)

    async def ensure_collection(self, name: str, vector_size: int) -> None:
        try:
            await self.create_collection(name, vector_size)
        except Exception:
            log.debug("qdrant_collection_already_exists", name=name)

    async def health_check(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception:
            log.warning("qdrant_health_check_failed")
            return False
