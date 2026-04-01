-- Migration 015: Add confidence, correction, and reasoning columns to human_interrupts.
-- Supports REQ-017 approval gates with confidence thresholds and correction capture.

ALTER TABLE human_interrupts
    ADD COLUMN IF NOT EXISTS confidence      FLOAT,
    ADD COLUMN IF NOT EXISTS threshold        FLOAT,
    ADD COLUMN IF NOT EXISTS correction       JSONB,
    ADD COLUMN IF NOT EXISTS reasoning        TEXT DEFAULT '';

-- Index for finding auto-approved vs manually-approved interrupts
CREATE INDEX IF NOT EXISTS idx_human_interrupts_confidence
    ON human_interrupts (confidence)
    WHERE confidence IS NOT NULL;
