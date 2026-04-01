-- Migration 015: Create notification_preferences table
--
-- Stores per-user opt-in/out preferences for notification channels
-- and event types, enabling centralised notification routing.

CREATE TABLE IF NOT EXISTS notification_preferences (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    channel_type    VARCHAR(50)  NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Each user can have at most one preference per event_type + channel_type.
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_prefs_user_event_channel
    ON notification_preferences (user_id, event_type, channel_type);

-- Fast lookups by user.
CREATE INDEX IF NOT EXISTS ix_notification_prefs_user_id
    ON notification_preferences (user_id);

-- Rollback:
-- DROP TABLE IF EXISTS notification_preferences;
