-- REQ-010: Coverage metrics storage
CREATE TABLE IF NOT EXISTS coverage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID,
    run_id UUID NOT NULL,
    project_id UUID,
    line_rate NUMERIC(5,4) NOT NULL DEFAULT 0,
    branch_rate NUMERIC(5,4) NOT NULL DEFAULT 0,
    lines_covered INT NOT NULL DEFAULT 0,
    lines_total INT NOT NULL DEFAULT 0,
    branches_covered INT NOT NULL DEFAULT 0,
    branches_total INT NOT NULL DEFAULT 0,
    raw_files JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coverage_metrics_run_id ON coverage_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_coverage_metrics_project_id ON coverage_metrics(project_id);
