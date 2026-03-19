"""PostgresArtifactStore — stores artifact content inline in Postgres."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from lintel.contracts.protocols.artifact_store import ArtifactRef

if TYPE_CHECKING:
    import asyncpg


class PostgresArtifactStore:
    """ArtifactStore that persists content inline in the Postgres entities table.

    Content is base64-encoded and stored in the JSONB ``data`` column alongside
    the existing ``CodeArtifact`` fields.  Storage metadata columns
    (``storage_backend``, ``storage_location``, ``size_bytes``, ``content_type``)
    are set on the same row.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        """Write content inline and return the artifact_id as location."""
        location = artifact_id
        content_type = str(metadata.get("content_type", "application/octet-stream"))
        size_bytes = len(content)
        encoded = base64.b64encode(content).decode("ascii")

        async with self._pool.acquire() as conn:
            # Update the existing entity row with storage metadata
            await conn.execute(
                """
                UPDATE entities
                SET storage_backend = $1,
                    storage_location = $2,
                    size_bytes = $3,
                    content_type = $4,
                    data = data || jsonb_build_object(
                        'storage_backend', $1,
                        'storage_location', $2,
                        'size_bytes', $3,
                        'content_type', $4,
                        'encoded_content', $5
                    ),
                    updated_at = now()
                WHERE kind = 'code_artifact' AND entity_id = $6
                """,
                "postgres",
                location,
                size_bytes,
                content_type,
                encoded,
                artifact_id,
            )
        return location

    async def retrieve(self, artifact_id: str) -> bytes:
        """Fetch content from inline storage."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT data
                FROM entities
                WHERE kind = 'code_artifact' AND entity_id = $1
                """,
                artifact_id,
            )
        if row is None:
            msg = f"Artifact {artifact_id} not found"
            raise KeyError(msg)

        data: dict[str, Any] = dict(row["data"]) if row["data"] else {}
        encoded = data.get("encoded_content")
        if encoded:
            return base64.b64decode(encoded)
        # Fallback: return the original content field as bytes
        content = data.get("content", "")
        return content.encode("utf-8") if isinstance(content, str) else bytes(content)

    async def get_backend(self, artifact_id: str) -> str:
        """Look up the storage_backend for an artifact."""
        async with self._pool.acquire() as conn:
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

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        """Query artifacts for a pipeline run and return ArtifactRef list."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_id, storage_backend, storage_location,
                       size_bytes, content_type, data
                FROM entities
                WHERE kind = 'code_artifact'
                  AND (data->>'run_id' = $1)
                """,
                pipeline_run_id,
            )
        refs = []
        for row in rows:
            data: dict[str, Any] = dict(row["data"]) if row["data"] else {}
            refs.append(
                ArtifactRef(
                    artifact_id=row["entity_id"],
                    storage_backend=row["storage_backend"] or "postgres",
                    location=row["storage_location"] or row["entity_id"],
                    size_bytes=row["size_bytes"] or 0,
                    content_type=row["content_type"]
                    or str(data.get("content_type", "application/octet-stream")),
                    pipeline_run_id=pipeline_run_id,
                )
            )
        return refs
