-- Migration 001: Create event store
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id       TEXT NOT NULL,
    stream_version  BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    schema_version  INT NOT NULL DEFAULT 1,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type      TEXT NOT NULL,
    actor_id        TEXT NOT NULL,
    correlation_id  UUID NOT NULL,
    causation_id    UUID,
    thread_ref      JSONB,
    payload         JSONB NOT NULL,
    payload_hash    TEXT,
    prev_hash       TEXT,
    idempotency_key TEXT,
    UNIQUE (stream_id, stream_version),
    UNIQUE (idempotency_key)
) PARTITION BY RANGE (occurred_at);

-- Create initial partition
CREATE TABLE events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Indexes
CREATE INDEX idx_events_stream ON events (stream_id, stream_version);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_correlation ON events (correlation_id);
CREATE INDEX idx_events_occurred ON events (occurred_at);
CREATE INDEX idx_events_thread_ref ON events USING GIN (thread_ref);

-- Notify trigger for event bridge
CREATE OR REPLACE FUNCTION notify_new_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_event', NEW.event_id::text || ':' || NEW.event_type);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER event_inserted AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION notify_new_event();
