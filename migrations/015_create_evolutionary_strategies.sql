-- REQ-034.2.2/034.2.3: Evolutionary strategy mutations & tournament selection
-- Stores agent strategy configurations with parent lineage for mutation tracking.

CREATE TABLE IF NOT EXISTS evolutionary_strategies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    config              JSONB NOT NULL DEFAULT '{}',
    parent_strategy_id  UUID REFERENCES evolutionary_strategies(id),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'pruned', 'promoted')),
    score               DOUBLE PRECISION,
    generation          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evolutionary_strategies_parent
    ON evolutionary_strategies (parent_strategy_id);

CREATE INDEX IF NOT EXISTS idx_evolutionary_strategies_status
    ON evolutionary_strategies (status);
