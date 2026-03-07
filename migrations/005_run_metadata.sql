-- Run metadata table for fast pipeline run queries
CREATE TABLE IF NOT EXISTS run_metadata (
    run_id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    trigger_type TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT,
    step_count INTEGER DEFAULT 0,
    thread_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_metadata_pipeline ON run_metadata(pipeline_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_metadata_status ON run_metadata(status);
