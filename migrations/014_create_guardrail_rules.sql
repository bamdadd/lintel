-- Migration 014: Create guardrail_rules table (GRD-7)
--
-- Stores configurable guardrail rules that evaluate domain events
-- and trigger actions (WARN, BLOCK, REQUIRE_APPROVAL).

CREATE TABLE IF NOT EXISTS guardrail_rules (
    id              UUID PRIMARY KEY,
    name            TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    condition       TEXT NOT NULL,
    action          TEXT NOT NULL
                    CHECK (action IN ('WARN', 'BLOCK', 'REQUIRE_APPROVAL')),
    threshold       NUMERIC,
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    is_default      BOOLEAN NOT NULL DEFAULT TRUE,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Default rules have unique names to prevent duplicates during seeding.
CREATE UNIQUE INDEX IF NOT EXISTS uq_guardrail_rules_default_name
    ON guardrail_rules (name) WHERE is_default = TRUE;

-- Fast lookup by event_type for engine evaluation.
CREATE INDEX IF NOT EXISTS ix_guardrail_rules_event_type
    ON guardrail_rules (event_type) WHERE enabled = TRUE;

-- Rollback:
-- DROP TABLE IF EXISTS guardrail_rules;
