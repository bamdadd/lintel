-- Migration 010: Create human_interrupts table for shared LangGraph interrupt infrastructure.
-- Used by F013 (editable reports), F017 (approval gates), and F018 (human worker nodes).

CREATE TABLE IF NOT EXISTS human_interrupts (
    id              UUID PRIMARY KEY,
    run_id          TEXT NOT NULL,
    stage           TEXT NOT NULL,
    interrupt_type  TEXT NOT NULL,          -- approval_gate | editable_report | human_task
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | resumed | timed_out
    deadline        TIMESTAMPTZ,
    resumed_by      TEXT,
    resume_input    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup by run + stage (resume API path parameters)
CREATE INDEX IF NOT EXISTS idx_human_interrupts_run_stage
    ON human_interrupts (run_id, stage);

-- Timeout poller: find pending interrupts past their deadline
CREATE INDEX IF NOT EXISTS idx_human_interrupts_status_deadline
    ON human_interrupts (status, deadline)
    WHERE status = 'pending' AND deadline IS NOT NULL;

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION update_human_interrupts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_human_interrupts_updated_at ON human_interrupts;
CREATE TRIGGER trg_human_interrupts_updated_at
    BEFORE UPDATE ON human_interrupts
    FOR EACH ROW
    EXECUTE FUNCTION update_human_interrupts_updated_at();
