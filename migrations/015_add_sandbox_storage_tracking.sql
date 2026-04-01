-- Migration 015: Add sandbox storage tracking columns (REQ-031)
--
-- Adds per-sandbox storage limit and usage tracking to the sandbox_metadata
-- table, plus a scheduled_cleanup_at column for deferred cleanup scheduling.

ALTER TABLE sandbox_metadata ADD COLUMN IF NOT EXISTS storage_limit_gb INTEGER NOT NULL DEFAULT 4;
ALTER TABLE sandbox_metadata ADD COLUMN IF NOT EXISTS storage_usage_bytes BIGINT;
ALTER TABLE sandbox_metadata ADD COLUMN IF NOT EXISTS storage_checked_at TIMESTAMPTZ;
ALTER TABLE sandbox_metadata ADD COLUMN IF NOT EXISTS scheduled_cleanup_at TIMESTAMPTZ;

-- Index for efficient cleanup queries (find sandboxes due for cleanup)
CREATE INDEX IF NOT EXISTS idx_sandbox_scheduled_cleanup
    ON sandbox_metadata (scheduled_cleanup_at)
    WHERE scheduled_cleanup_at IS NOT NULL;
