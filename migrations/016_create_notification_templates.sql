-- Migration 016: Create notification_templates table
--
-- Stores reusable notification body templates with variable
-- substitution, keyed by name and channel type.

CREATE TABLE IF NOT EXISTS notification_templates (
    id                UUID PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    channel_type      VARCHAR(50)  NOT NULL,
    body_template     TEXT NOT NULL,
    subject_template  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Template names are unique per channel type.
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_templates_name_channel
    ON notification_templates (name, channel_type);

-- Rollback:
-- DROP TABLE IF EXISTS notification_templates;
