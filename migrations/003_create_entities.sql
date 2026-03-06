-- Migration 003: Generic entity store for CRUD resources
CREATE TABLE IF NOT EXISTS entities (
    kind        TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    data        JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities (kind);
CREATE INDEX IF NOT EXISTS idx_entities_data ON entities USING GIN (data);
