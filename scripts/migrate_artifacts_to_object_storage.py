"""Background migration: move large artifacts from inline Postgres to object storage.

Usage:
    uv run python scripts/migrate_artifacts_to_object_storage.py \
        --database-url postgresql://... \
        --bucket lintel-artifacts \
        [--endpoint-url http://localhost:9000] \
        [--threshold-bytes 1048576] \
        [--batch-size 50] \
        [--dry-run]

This script:
1. Queries artifacts stored inline in Postgres above the size threshold
2. Uploads their content to S3/MinIO
3. Updates the Postgres row to point to the S3 location
4. Removes the inline encoded_content from the JSONB data column

Safe to run multiple times — skips artifacts already migrated to s3.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def migrate(
    database_url: str,
    bucket: str,
    endpoint_url: str | None,
    threshold_bytes: int,
    batch_size: int,
    dry_run: bool,
) -> None:
    import aioboto3
    import asyncpg

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
    assert pool is not None
    session = aioboto3.Session()

    try:
        # Find artifacts that are inline and above threshold
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_id, data, size_bytes
                FROM entities
                WHERE kind = 'code_artifact'
                  AND (storage_backend = 'postgres' OR storage_backend IS NULL)
                  AND size_bytes > $1
                ORDER BY size_bytes DESC
                LIMIT $2
                """,
                threshold_bytes,
                batch_size,
            )

        if not rows:
            logger.info("No artifacts above threshold to migrate.")
            return

        logger.info("Found %d artifacts to migrate (dry_run=%s)", len(rows), dry_run)

        s3_kwargs: dict[str, str] = {}
        if endpoint_url:
            s3_kwargs["endpoint_url"] = endpoint_url

        migrated = 0
        for row in rows:
            artifact_id = row["entity_id"]
            data = dict(row["data"]) if row["data"] else {}
            encoded = data.get("encoded_content")

            if not encoded:
                # Try raw content field
                raw_content = data.get("content", "")
                content = (
                    raw_content.encode("utf-8") if isinstance(raw_content, str) else bytes(raw_content)
                )
            else:
                content = base64.b64decode(encoded)

            if len(content) <= threshold_bytes:
                logger.debug("Skipping %s — content %d bytes below threshold", artifact_id, len(content))
                continue

            key = f"artifacts/{artifact_id}"
            s3_uri = f"s3://{bucket}/{key}"
            content_type = data.get("content_type", "application/octet-stream")

            if dry_run:
                logger.info("[DRY RUN] Would migrate %s (%d bytes) -> %s", artifact_id, len(content), s3_uri)
                migrated += 1
                continue

            # Upload to S3
            async with session.client("s3", **s3_kwargs) as s3:
                await s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=str(content_type),
                )

            # Update Postgres: set backend to s3, remove inline content
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE entities
                    SET storage_backend = 's3',
                        storage_location = $1,
                        data = data - 'encoded_content',
                        updated_at = now()
                    WHERE kind = 'code_artifact' AND entity_id = $2
                    """,
                    s3_uri,
                    artifact_id,
                )

            migrated += 1
            logger.info("Migrated %s (%d bytes) -> %s", artifact_id, len(content), s3_uri)

        logger.info("Migration complete: %d/%d artifacts migrated", migrated, len(rows))

    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate large artifacts to object storage")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--bucket", required=True, help="S3/MinIO bucket name")
    parser.add_argument("--endpoint-url", default=None, help="S3-compatible endpoint URL (for MinIO)")
    parser.add_argument("--threshold-bytes", type=int, default=1_048_576, help="Size threshold in bytes (default: 1MB)")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of artifacts per batch")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    asyncio.run(
        migrate(
            database_url=args.database_url,
            bucket=args.bucket,
            endpoint_url=args.endpoint_url,
            threshold_bytes=args.threshold_bytes,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
