-- Add TIMED_OUT to stage status and step_timeout_seconds to run metadata.
--
-- The run_metadata.status column uses plain TEXT, so no enum alteration is needed.
-- We add step_timeout_seconds so per-pipeline timeout overrides can be persisted.
ALTER TABLE run_metadata ADD COLUMN IF NOT EXISTS step_timeout_seconds INTEGER;
