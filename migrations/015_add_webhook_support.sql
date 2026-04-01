-- REQ-026: Add webhook support for git event listeners
-- Adds webhook_secret to repositories and creates webhook_deliveries dedup table.

ALTER TABLE entities
    ADD COLUMN IF NOT EXISTS webhook_secret TEXT;

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    delivery_id TEXT PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for cleanup of old deliveries
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_received_at
    ON webhook_deliveries (received_at);
