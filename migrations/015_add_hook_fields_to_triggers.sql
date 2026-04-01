-- Migration 015: Add hook fields to triggers table for REQ-012 hook system.
-- Extends triggers with hook_type, event_pattern, condition, max_chain_depth.

DO $$
BEGIN
    -- Add hook_type column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'triggers' AND column_name = 'hook_type'
    ) THEN
        ALTER TABLE triggers ADD COLUMN hook_type VARCHAR(10);
    END IF;

    -- Add event_pattern column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'triggers' AND column_name = 'event_pattern'
    ) THEN
        ALTER TABLE triggers ADD COLUMN event_pattern VARCHAR(255);
    END IF;

    -- Add condition column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'triggers' AND column_name = 'condition'
    ) THEN
        ALTER TABLE triggers ADD COLUMN condition TEXT;
    END IF;

    -- Add max_chain_depth column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'triggers' AND column_name = 'max_chain_depth'
    ) THEN
        ALTER TABLE triggers ADD COLUMN max_chain_depth INT DEFAULT 5;
    END IF;
END
$$;

-- CHECK constraint on hook_type to enforce valid values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_name = 'triggers' AND constraint_name = 'chk_hook_type'
    ) THEN
        ALTER TABLE triggers ADD CONSTRAINT chk_hook_type
            CHECK (hook_type IS NULL OR hook_type IN ('pre', 'post'));
    END IF;
END
$$;

-- Index on event_pattern for efficient pattern lookups
CREATE INDEX IF NOT EXISTS idx_triggers_event_pattern
    ON triggers (event_pattern)
    WHERE event_pattern IS NOT NULL;
