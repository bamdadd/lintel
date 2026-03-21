-- Migration 012: Add missing indexes and cancelled status support for human_interrupts.
--
-- Migration 010 created the base table with columns: id, run_id, stage,
-- interrupt_type, payload, status, deadline, resumed_by, resume_input,
-- created_at, updated_at plus indexes on (run_id, stage) and
-- (status, deadline) WHERE status='pending'.
--
-- This migration adds:
-- 1. Index on (run_id, status) for the resume API query pattern
-- 2. 'cancelled' as a valid status value (CHECK constraint)

-- Fast lookup by run_id + status for the resume API and status queries.
CREATE INDEX IF NOT EXISTS idx_human_interrupts_run_status
    ON human_interrupts (run_id, status);

-- Add CHECK constraint to enforce valid status values.
-- Using DO block to avoid failure if constraint already exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_human_interrupts_status'
    ) THEN
        ALTER TABLE human_interrupts
            ADD CONSTRAINT chk_human_interrupts_status
            CHECK (status IN ('pending', 'resumed', 'timed_out', 'cancelled'));
    END IF;
END $$;
