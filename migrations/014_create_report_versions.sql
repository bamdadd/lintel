-- Migration 014: Create report_versions table for persistent report version storage.
-- Tracks versioned markdown reports produced at each pipeline stage, supporting
-- AI-generated originals, human edits, and regenerations with content deduplication.

CREATE TABLE IF NOT EXISTS report_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          TEXT NOT NULL,
    stage_id        TEXT NOT NULL,
    stage_name      TEXT NOT NULL DEFAULT '',
    version_number  INTEGER NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL DEFAULT '',
    editor          TEXT NOT NULL DEFAULT 'ai',
    edit_type       TEXT NOT NULL DEFAULT 'edit',
    edit_summary    TEXT DEFAULT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent duplicate version numbers for the same run + stage
ALTER TABLE report_versions
    ADD CONSTRAINT uq_report_versions_run_stage_version
    UNIQUE (run_id, stage_id, version_number);

-- Fast lookup by run + stage + version number
CREATE INDEX IF NOT EXISTS idx_report_versions_run_stage
    ON report_versions (run_id, stage_id, version_number);

-- List all versions across a pipeline run
CREATE INDEX IF NOT EXISTS idx_report_versions_run_id
    ON report_versions (run_id);
