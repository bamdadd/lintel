-- Review reports table for the review-and-improve workflow (REQ-006).
-- Stores structured review reports with per-file scores across 5 dimensions.

CREATE TABLE IF NOT EXISTS review_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID NOT NULL,
    repo_id         UUID NOT NULL,
    contributor_id  UUID,
    commit_shas     TEXT[] NOT NULL DEFAULT '{}',
    report_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    aggregate_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_backend VARCHAR(50) NOT NULL DEFAULT 'postgres',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_reports_pipeline_run
    ON review_reports (pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_review_reports_repo
    ON review_reports (repo_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_reports_contributor
    ON review_reports (contributor_id, created_at DESC)
    WHERE contributor_id IS NOT NULL;
