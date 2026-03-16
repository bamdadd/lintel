"""ObjectArtifactStore — stores artifact content in S3/MinIO object storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.contracts.protocols.artifact_store import ArtifactRef

if TYPE_CHECKING:
    import aioboto3
    import asyncpg


class ObjectArtifactStore:
    """ArtifactStore that persists content in S3/MinIO and metadata in Postgres.

    Content bytes are uploaded to S3 under ``artifacts/{artifact_id}``.
    The Postgres row is updated with ``storage_backend='s3'`` and the S3 URI
    so retrieval can locate the object.
    """

    def __init__(
        self,
        session: aioboto3.Session,
        pool: asyncpg.Pool,
        bucket: str,
        endpoint_url: str | None = None,
    ) -> None:
        self._session = session
        self._pool = pool
        self._bucket = bucket
        self._endpoint_url = endpoint_url

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        """Upload content to S3 and write metadata to Postgres."""
        key = f"artifacts/{artifact_id}"
        s3_uri = f"s3://{self._bucket}/{key}"
        content_type = str(metadata.get("content_type", "application/octet-stream"))
        size_bytes = len(content)

        # Upload to S3
        s3_kwargs: dict[str, Any] = {}
        if self._endpoint_url:
            s3_kwargs["endpoint_url"] = self._endpoint_url
        async with self._session.client("s3", **s3_kwargs) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )

        # Update Postgres metadata
        async with self._pool.acquire() as conn:
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
                        'content_type', $4
                    ),
                    updated_at = now()
                WHERE kind = 'code_artifact' AND entity_id = $5
                """,
                "s3",
                s3_uri,
                size_bytes,
                content_type,
                artifact_id,
            )
        return s3_uri

    async def retrieve(self, artifact_id: str) -> bytes:
        """Fetch S3 location from Postgres, then download the object."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT storage_location
                FROM entities
                WHERE kind = 'code_artifact' AND entity_id = $1
                """,
                artifact_id,
            )
        if row is None:
            msg = f"Artifact {artifact_id} not found"
            raise KeyError(msg)

        location: str = row["storage_location"]
        # Parse s3://bucket/key
        without_scheme = location.removeprefix("s3://")
        bucket, _, key = without_scheme.partition("/")

        s3_kwargs: dict[str, Any] = {}
        if self._endpoint_url:
            s3_kwargs["endpoint_url"] = self._endpoint_url
        async with self._session.client("s3", **s3_kwargs) as s3:
            resp = await s3.get_object(Bucket=bucket, Key=key)
            body = await resp["Body"].read()
        return bytes(body)

    async def list_refs(self, pipeline_run_id: str) -> list[ArtifactRef]:
        """Query Postgres metadata (no S3 calls needed)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_id, storage_backend, storage_location,
                       size_bytes, content_type
                FROM entities
                WHERE kind = 'code_artifact'
                  AND (data->>'run_id' = $1)
                """,
                pipeline_run_id,
            )
        return [
            ArtifactRef(
                artifact_id=row["entity_id"],
                storage_backend=row["storage_backend"] or "s3",
                location=row["storage_location"] or "",
                size_bytes=row["size_bytes"] or 0,
                content_type=row["content_type"] or "application/octet-stream",
                pipeline_run_id=pipeline_run_id,
            )
            for row in rows
        ]
