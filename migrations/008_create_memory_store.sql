CREATE TYPE memory_type_enum AS ENUM ('long_term', 'episodic');

CREATE TABLE memory_facts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id),
    memory_type         memory_type_enum NOT NULL,
    fact_type           VARCHAR(100) NOT NULL,
    content             TEXT NOT NULL,
    embedding_id        VARCHAR(255),
    source_workflow_id  UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_memory_facts_project_id ON memory_facts(project_id);
CREATE INDEX idx_memory_facts_memory_type ON memory_facts(memory_type);
CREATE INDEX idx_memory_facts_project_id_memory_type ON memory_facts(project_id, memory_type);
CREATE INDEX idx_memory_facts_fact_type ON memory_facts(fact_type);
