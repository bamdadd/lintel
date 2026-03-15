-- Migration 008: Add channel_type support and channel_connections table
-- Supports multi-channel adapter architecture (Slack, Telegram, etc.)

-- 1. Add channel_type column to events table for ThreadRef persistence
ALTER TABLE events ADD COLUMN IF NOT EXISTS channel_type TEXT DEFAULT 'slack';

-- 2. Backfill existing rows with 'slack' channel type
UPDATE events SET channel_type = 'slack' WHERE channel_type IS NULL;

-- 3. Create channel_connections table for per-channel bot configuration
CREATE TABLE IF NOT EXISTS channel_connections (
    connection_id TEXT PRIMARY KEY,
    channel_type TEXT NOT NULL,
    credential_ref TEXT NOT NULL DEFAULT '',
    webhook_secret_ref TEXT NOT NULL DEFAULT '',
    webhook_url TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT true,
    bot_username TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Index for quick lookup by channel type
CREATE INDEX IF NOT EXISTS idx_channel_connections_type ON channel_connections(channel_type);
