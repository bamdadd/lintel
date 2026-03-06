CREATE TABLE IF NOT EXISTS pii_vault (
    thread_ref   TEXT NOT NULL,
    placeholder  TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    encrypted_raw BYTEA NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revealed_at  TIMESTAMPTZ,
    revealed_by  TEXT,
    PRIMARY KEY (thread_ref, placeholder)
);
