-- REQ-034.3: Knowledge graph schema (observations, edges, syntheses, playbooks)

CREATE TABLE IF NOT EXISTS observations (
    observation_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL,
    project_id      UUID NOT NULL,
    content         TEXT NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    synthesized_at  TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_observations_run_id ON observations (run_id);
CREATE INDEX idx_observations_project_id ON observations (project_id);
CREATE INDEX idx_observations_unsynthesized
    ON observations (extracted_at)
    WHERE synthesized_at IS NULL;

CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_id     UUID NOT NULL REFERENCES observations (observation_id),
    to_id       UUID NOT NULL REFERENCES observations (observation_id),
    edge_type   TEXT NOT NULL CHECK (edge_type IN ('inspired_by', 'contradicts', 'extends', 'supersedes')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (from_id, to_id, edge_type)
);

CREATE INDEX idx_knowledge_edges_from_id ON knowledge_edges (from_id);
CREATE INDEX idx_knowledge_edges_to_id ON knowledge_edges (to_id);

CREATE TABLE IF NOT EXISTS syntheses (
    synthesis_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis              TEXT NOT NULL,
    source_observation_ids  UUID[] NOT NULL DEFAULT '{}',
    project_ids             UUID[] NOT NULL DEFAULT '{}',
    confidence_score        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS playbooks (
    playbook_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title                   TEXT NOT NULL,
    strategy                TEXT NOT NULL DEFAULT '',
    source_synthesis_ids    UUID[] NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
