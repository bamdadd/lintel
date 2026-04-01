-- Migration 015: Create approval projection and correction record tables.
-- Used by ApprovalRequestProjection and CorrectionProjection (REQ-017).

CREATE TABLE IF NOT EXISTS approval_request_projections (
    approval_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    stage           TEXT NOT NULL DEFAULT '',
    gate_type       TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    confidence      FLOAT,
    threshold       FLOAT,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT DEFAULT '',
    decision        TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_approval_proj_run_id
    ON approval_request_projections (run_id);

CREATE INDEX IF NOT EXISTS idx_approval_proj_status
    ON approval_request_projections (status);

CREATE TABLE IF NOT EXISTS correction_records (
    correction_id   TEXT PRIMARY KEY,
    approval_id     TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    stage           TEXT NOT NULL DEFAULT '',
    original_output JSONB,
    correction      JSONB,
    reasoning       TEXT DEFAULT '',
    corrected_by    TEXT DEFAULT '',
    corrected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_correction_records_run_id
    ON correction_records (run_id);

CREATE INDEX IF NOT EXISTS idx_correction_records_approval_id
    ON correction_records (approval_id);
