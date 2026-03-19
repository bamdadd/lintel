-- REQ-010: Test results storage
-- Preamble: extend artifacts table
ALTER TABLE entities ADD COLUMN IF NOT EXISTS artifact_type VARCHAR DEFAULT 'generic';
ALTER TABLE entities ADD COLUMN IF NOT EXISTS storage_backend VARCHAR DEFAULT 'postgres';

CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID,
    run_id UUID NOT NULL,
    project_id UUID,
    total_tests INT NOT NULL DEFAULT 0,
    passed INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    errors INT NOT NULL DEFAULT 0,
    skipped INT NOT NULL DEFAULT 0,
    duration_ms INT NOT NULL DEFAULT 0,
    raw_suites JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON test_results(run_id);
CREATE INDEX IF NOT EXISTS idx_test_results_project_id ON test_results(project_id);
CREATE INDEX IF NOT EXISTS idx_test_results_artifact_id ON test_results(artifact_id);
