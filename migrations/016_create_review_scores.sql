-- Review scores table for trend tracking per repo/contributor/dimension (REQ-006).
-- Supports time-series queries for score trends across 5 review dimensions.

CREATE TABLE IF NOT EXISTS review_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id         UUID NOT NULL,
    contributor_id  UUID,
    pipeline_run_id UUID NOT NULL,
    dimension       VARCHAR(50) NOT NULL
                    CHECK (dimension IN ('correctness', 'security', 'performance', 'maintainability', 'architecture')),
    score           NUMERIC(5,2) NOT NULL DEFAULT 0.0,
    severity        VARCHAR(20) NOT NULL DEFAULT 'info',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_scores_repo_dim_time
    ON review_scores (repo_id, dimension, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_scores_contributor_dim_time
    ON review_scores (contributor_id, dimension, recorded_at DESC)
    WHERE contributor_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_review_scores_pipeline_run
    ON review_scores (pipeline_run_id);
