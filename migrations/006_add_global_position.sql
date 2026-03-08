-- Migration 006: Add global_position for consistent cross-stream ordering
-- Used by catch-up subscriptions to track replay progress

-- Create a sequence for gap-free global ordering
CREATE SEQUENCE IF NOT EXISTS events_global_position_seq;

-- Add global_position column
ALTER TABLE events ADD COLUMN IF NOT EXISTS global_position BIGINT;

-- Backfill existing rows (order by occurred_at for historical consistency)
WITH ordered AS (
    SELECT event_id, occurred_at,
           nextval('events_global_position_seq') AS pos
    FROM events
    ORDER BY occurred_at, stream_version
)
UPDATE events SET global_position = ordered.pos
FROM ordered
WHERE events.event_id = ordered.event_id
  AND events.occurred_at = ordered.occurred_at
  AND events.global_position IS NULL;

-- Set default for new rows
ALTER TABLE events ALTER COLUMN global_position SET DEFAULT nextval('events_global_position_seq');

-- Index for catch-up subscription queries
CREATE INDEX IF NOT EXISTS idx_events_global_position ON events (global_position);
