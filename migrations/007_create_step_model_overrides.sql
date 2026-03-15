-- Migration 007: Per-step model overrides for projects (REQ-021)
CREATE TABLE IF NOT EXISTS project_step_model_overrides (
    project_id  UUID        NOT NULL,
    node_type   TEXT        NOT NULL,
    provider    TEXT        NOT NULL,
    model       TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, node_type),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_step_model_overrides_project_id
    ON project_step_model_overrides (project_id);
