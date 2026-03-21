-- Subscriber position tracking for durable catch-up subscriptions.
-- Each subscriber records its last successfully processed global_position
-- so it can resume from that point after restart.

CREATE TABLE IF NOT EXISTS subscriber_positions (
    subscriber_id  TEXT        PRIMARY KEY,
    last_position  BIGINT      NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE subscriber_positions IS
    'Tracks the last processed global_position per subscriber for catch-up resumption';
