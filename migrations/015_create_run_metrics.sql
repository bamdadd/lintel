-- REQ-034.2.1: Run-level metrics capture
-- Stores per-run performance measurements (latency, tokens, errors, etc.)

CREATE TABLE IF NOT EXISTS run_metrics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    unit        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_metrics_run_id
    ON run_metrics (run_id);

CREATE INDEX IF NOT EXISTS idx_run_metrics_metric_name
    ON run_metrics (metric_name);
