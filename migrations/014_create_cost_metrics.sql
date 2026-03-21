-- 014_create_cost_metrics.sql
-- Raw event log and aggregated cost metric tables for LLM call tracking.

-- 1. Raw model call events (append-only log)
CREATE TABLE IF NOT EXISTS model_call_events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE,
    model           TEXT NOT NULL,
    input_tokens    BIGINT NOT NULL DEFAULT 0,
    output_tokens   BIGINT NOT NULL DEFAULT 0,
    cost_usd        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    agent_role      TEXT NOT NULL DEFAULT '',
    run_id          TEXT,
    stage           TEXT,
    project_id      TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_call_events_run_id
    ON model_call_events (run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_model_call_events_project_id
    ON model_call_events (project_id) WHERE project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_model_call_events_stage
    ON model_call_events (stage) WHERE stage IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_model_call_events_occurred_at
    ON model_call_events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_model_call_events_agent_role
    ON model_call_events (agent_role) WHERE agent_role != '';

-- 2. Aggregated totals per pipeline run
CREATE TABLE IF NOT EXISTS cost_metrics_by_run (
    run_id              TEXT PRIMARY KEY,
    total_cost_usd      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_input_tokens  BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    call_count          INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Aggregated totals per run + stage
CREATE TABLE IF NOT EXISTS cost_metrics_by_stage (
    run_id              TEXT NOT NULL,
    stage               TEXT NOT NULL,
    total_cost_usd      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_input_tokens  BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    call_count          INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, stage)
);

-- 4. Aggregated daily totals per project
CREATE TABLE IF NOT EXISTS cost_metrics_by_project_daily (
    project_id          TEXT NOT NULL,
    day                 DATE NOT NULL,
    total_cost_usd      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_input_tokens  BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    call_count          INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, day)
);

CREATE INDEX IF NOT EXISTS idx_cost_project_daily_day
    ON cost_metrics_by_project_daily (day);

-- 5. Aggregated totals per agent role (optionally scoped to project)
CREATE TABLE IF NOT EXISTS cost_metrics_by_agent_role (
    agent_role          TEXT NOT NULL,
    project_id          TEXT NOT NULL DEFAULT '',
    total_cost_usd      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_input_tokens  BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    call_count          INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_role, project_id)
);
