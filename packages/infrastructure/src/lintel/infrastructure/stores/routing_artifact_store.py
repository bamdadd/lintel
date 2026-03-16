"""RoutingArtifactStore — delegates to postgres or object store based on size."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.protocols.artifact_store import ArtifactRef, ArtifactStore


class RoutingArtifactStore:
    """ArtifactStore wrapper that routes to postgres or object storage by size.

    Content smaller than ``size_threshold_bytes`` is stored inline in Postgres.
    Larger content is delegated to the object store (S3/MinIO).

    This class structurally satisfies the ``ArtifactStore`` Protocol.
    """

    def __init__(
        self,
        postgres_store: ArtifactStore,
        object_store: ArtifactStore,
        size_threshold_bytes: int = 1_048_576,
    ) -> None:
        self._postgres_store = postgres_store
        self._object_store = object_store
        self._size_threshold_bytes = size_threshold_bytes

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        """Route to object store if content exceeds threshold, else postgres."""
        if len(content) > self._size_threshold_bytes:
            return await self._object_store.store(artifact_id, content, metadata)
        return await self._postgres_store.store(artifact_id, content, metadata)

    async def retrieve(self, artifact_id: str) -> bytes:
        """Look up storage_backend from postgres metadata, then delegate."""
        # The postgres store always has the metadata; check backend to decide
        # which store to use for content retrieval.
        backend = await self._get_backend(artifact_id)
        if backend == "s3":
            return await self._object_store.retrieve(artifact_id)
        return await self._postgres_store.retrieve(artifact_id)

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        """Metadata is always in Postgres, so delegate there."""
        return await self._postgres_store.list_refs(pipeline_run_id)

    async def _get_backend(self, artifact_id: str) -> str:
        """Look up the storage_backend for an artifact from postgres metadata."""
        # Use the postgres store's list to find the ref (or query directly)
        # Since both stores share the same DB, we can query via postgres_store's pool
        store: Any = self._postgres_store
        if hasattr(store, "_pool"):
            async with store._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT storage_backend
                    FROM entities
                    WHERE kind = 'code_artifact' AND entity_id = $1
                    """,
                    artifact_id,
                )
                if row is not None:
                    return str(row["storage_backend"] or "postgres")
        return "postgres"
