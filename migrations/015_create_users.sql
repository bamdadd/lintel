-- REQ-033: Authentication — Phase 1
-- Create the auth users table for built-in authentication.

CREATE TABLE IF NOT EXISTS auth_users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT            NOT NULL UNIQUE,
    display_name    TEXT            NOT NULL,
    role            TEXT            NOT NULL CHECK (role IN ('member', 'admin', 'superuser')),
    hashed_password TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users (email);
