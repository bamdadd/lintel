-- REQ-010: Quality gate rules configuration
CREATE TABLE IF NOT EXISTS quality_gate_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    rule_type VARCHAR NOT NULL,
    threshold NUMERIC NOT NULL,
    severity VARCHAR NOT NULL DEFAULT 'error',
    enabled BOOL NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quality_gate_rules_project_id ON quality_gate_rules(project_id);
