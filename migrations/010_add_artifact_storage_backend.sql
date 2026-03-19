-- Migration 010: Add artifact storage backend metadata columns
--
-- Purpose: Extend artifacts stored in the entities table with storage metadata
-- to support routing content to different backends (inline Postgres vs S3/MinIO).
-- These columns are added to the entities table and used when kind='code_artifact'.
--
-- The new columns are:
--   storage_backend  - 'postgres' (inline) or 's3' (object storage)
--   storage_location - the S3 URI or inline reference identifier
--   size_bytes       - content size for routing decisions
--   content_type     - MIME type of the stored content
--
-- Safe rollback:
--   ALTER TABLE entities DROP COLUMN IF EXISTS storage_backend;
--   ALTER TABLE entities DROP COLUMN IF EXISTS storage_location;
--   ALTER TABLE entities DROP COLUMN IF EXISTS size_bytes;
--   ALTER TABLE entities DROP COLUMN IF EXISTS content_type;

ALTER TABLE entities ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32) NOT NULL DEFAULT 'postgres';
ALTER TABLE entities ADD COLUMN IF NOT EXISTS storage_location TEXT;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS size_bytes BIGINT;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS content_type VARCHAR(255);
