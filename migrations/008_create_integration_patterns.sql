-- Migration 008: Create integration pattern tables (REQ-005)

CREATE TABLE IF NOT EXISTS integration_maps (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    repository_id   TEXT        NOT NULL,
    workflow_run_id TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_maps_repository_id
    ON integration_maps (repository_id);

CREATE TABLE IF NOT EXISTS service_nodes (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    integration_map_id  UUID        NOT NULL,
    service_name        TEXT        NOT NULL,
    language            TEXT        NOT NULL,
    metadata            JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_service_nodes_integration_map_id
    ON service_nodes (integration_map_id);

CREATE TABLE IF NOT EXISTS integration_edges (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    integration_map_id  UUID        NOT NULL,
    source_node_id      UUID        NOT NULL,
    target_node_id      UUID        NOT NULL,
    integration_type    TEXT        NOT NULL,
    protocol            TEXT        NOT NULL,
    metadata            JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_integration_edges_integration_map_id
    ON integration_edges (integration_map_id);

CREATE TABLE IF NOT EXISTS pattern_catalogue (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    integration_map_id  UUID        NOT NULL,
    pattern_type        TEXT        NOT NULL,
    pattern_name        TEXT        NOT NULL,
    occurrences         INT         NOT NULL DEFAULT 0,
    details             JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pattern_catalogue_integration_map_id
    ON pattern_catalogue (integration_map_id);

CREATE TABLE IF NOT EXISTS antipattern_detections (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    integration_map_id  UUID        NOT NULL,
    antipattern_type    TEXT        NOT NULL,
    severity            TEXT        NOT NULL,
    affected_nodes      JSONB       NOT NULL DEFAULT '[]',
    description         TEXT        NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_antipattern_detections_integration_map_id
    ON antipattern_detections (integration_map_id);

CREATE TABLE IF NOT EXISTS service_coupling_scores (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    integration_map_id  UUID        NOT NULL,
    service_node_id     UUID        NOT NULL,
    afferent_coupling   INT         NOT NULL DEFAULT 0,
    efferent_coupling   INT         NOT NULL DEFAULT 0,
    instability         FLOAT       NOT NULL DEFAULT 0.0,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_coupling_scores_integration_map_id
    ON service_coupling_scores (integration_map_id);
