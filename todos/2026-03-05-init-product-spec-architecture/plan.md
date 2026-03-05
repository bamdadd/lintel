# Lintel Implementation Plan

**Selected Option:** Option B — Event-Sourced Modular Monolith with LangGraph orchestration
**Tech Areas:** python-backend, infrastructure, slack-integration, similar-oss
**Research:** [research.md](./research.md)

---

## 1. Architecture

### 1.1 System Overview

Lintel is a modular monolith deployed as a single FastAPI service for v0.1. It provides multi-agent AI collaboration through Slack threads, with event sourcing for auditability, Presidio-based PII protection, LangGraph workflow orchestration, and Docker/devcontainer sandbox isolation. All 12 logical service boundaries exist as Python modules with Protocol-based interfaces, enabling future extraction into independent services.

**ASCII Diagram:**
```
                                 LINTEL MODULAR MONOLITH (single process)
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                                                                              │
 │  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
 │  │   Slack      │──▶│  PII         │──▶│  Event       │──▶│  Workflow     │  │
 │  │   Adapter    │   │  Firewall    │   │  Store       │   │  Engine      │  │
 │  │  (Bolt)      │   │  (Presidio)  │   │  (Postgres)  │   │  (LangGraph) │  │
 │  └──────┬───────┘   └──────────────┘   └──────┬───────┘   └──────┬───────┘  │
 │         │                                      │                  │          │
 │         │           ┌──────────────┐   ┌──────┴───────┐   ┌──────┴───────┐  │
 │         │           │  Model       │   │  Projections │   │  Agent       │  │
 │         │           │  Router      │   │  (Read       │   │  Runtime     │  │
 │         │           │  (litellm)   │   │   Models)    │   │              │  │
 │         │           └──────────────┘   └──────────────┘   └──────┬───────┘  │
 │         │                                                        │          │
 │         │           ┌──────────────┐   ┌──────────────┐   ┌──────┴───────┐  │
 │         │           │  Skill       │   │  Policy &    │   │  Sandbox     │  │
 │         │           │  Registry    │   │  Identity    │   │  Manager     │  │
 │         │           └──────────────┘   └──────────────┘   └──────┬───────┘  │
 │         │                                                        │          │
 │  ┌──────┴───────┐                      ┌──────────────┐   ┌──────┴───────┐  │
 │  │  Repo        │                      │  Observ-     │   │  PII Vault   │  │
 │  │  Provider    │                      │  ability     │   │  (encrypted) │  │
 │  │  (GitHub)    │                      │  (OTel)      │   │              │  │
 │  └──────────────┘                      └──────────────┘   └──────────────┘  │
 │                                                                              │
 └──────────────────────────────────────────────────────────────────────────────┘
         │                          │                               │
         ▼                          ▼                               ▼
   ┌───────────┐            ┌───────────┐                   ┌───────────────┐
   │  Slack    │            │ Postgres  │                   │  Docker       │
   │  API      │            │ (events + │                   │  (sandboxes)  │
   └───────────┘            │  views)   │                   └───────────────┘
                            └───────────┘
```

**Mermaid Diagram:**
```mermaid
graph TB
    subgraph External["External Services"]
        SLACK[Slack API]
        GH[GitHub API]
        LLM[LLM Providers]
        DOCKER[Docker Engine]
    end

    subgraph Lintel["Lintel Modular Monolith"]
        subgraph Gateway["Channel Gateway"]
            SA[Slack Adapter<br/>slack-bolt]
        end

        subgraph Security["Security Layer"]
            PII[PII Firewall<br/>Presidio]
            VAULT[PII Vault<br/>encrypted]
            POLICY[Policy & Identity<br/>RBAC]
        end

        subgraph Core["Core Infrastructure"]
            ES[Event Store<br/>Postgres append-only]
            PROJ[Projections<br/>Read Models]
            OBS[Observability<br/>OpenTelemetry]
        end

        subgraph Orchestration["Orchestration"]
            WF[Workflow Engine<br/>LangGraph]
            AR[Agent Runtime]
            MR[Model Router<br/>litellm]
            SR[Skill Registry]
        end

        subgraph Execution["Execution"]
            SM[Sandbox Manager]
            RP[Repo Provider<br/>GitHub]
        end
    end

    SLACK <--> SA
    SA --> PII
    PII --> ES
    PII --> VAULT
    ES --> WF
    ES --> PROJ
    WF --> AR
    AR --> MR
    AR --> SR
    AR --> SM
    MR --> LLM
    SM --> DOCKER
    RP --> GH
    POLICY --> WF
    OBS -.-> ES

    style Security fill:#ffcccc
    style Core fill:#cce5ff
    style Orchestration fill:#ccffcc
    style Execution fill:#fff2cc
```

### 1.2 Component Boundaries

| Component | Responsibility | Tech Area | New/Modify | Module Path |
|-----------|---------------|-----------|------------|-------------|
| Contracts | Event envelope, event types, Protocols, shared types | python-backend | New | `src/lintel/contracts/` |
| Event Store | Append-only Postgres persistence, optimistic concurrency | python-backend | New | `src/lintel/infrastructure/event_store/` |
| PII Firewall | Presidio detection, anonymization, fail-closed | python-backend | New | `src/lintel/infrastructure/pii/` |
| PII Vault | Encrypted placeholder-to-raw mapping | python-backend | New | `src/lintel/infrastructure/vault/` |
| Slack Adapter | Bolt integration, event translation, Block Kit | slack-integration | New | `src/lintel/infrastructure/channels/slack/` |
| Workflow Engine | LangGraph graph definitions, checkpointing | python-backend | New | `src/lintel/workflows/` |
| Agent Runtime | Agent step execution, tool routing | python-backend | New | `src/lintel/agents/` |
| Model Router | Provider selection, litellm integration | python-backend | New | `src/lintel/infrastructure/models/` |
| Skill Registry | Dynamic skill registration, invocation | python-backend | New | `src/lintel/skills/` |
| Sandbox Manager | Docker/devcontainer lifecycle | infrastructure | New | `src/lintel/infrastructure/sandbox/` |
| Repo Provider | GitHub Git/PR operations | python-backend | New | `src/lintel/infrastructure/repos/` |
| Policy & Identity | RBAC, approval gates | python-backend | New | `src/lintel/domain/policy.py` |
| Projections | Thread status, task backlog read models | python-backend | New | `src/lintel/projections/` |
| Observability | Structured logging, tracing, metrics | infrastructure | New | `src/lintel/infrastructure/observability/` |
| API Layer | FastAPI routes, middleware, DI wiring | python-backend | New | `src/lintel/api/` |

### 1.3 Data Flow

**ASCII:**
```
Slack Message
     │
     ▼
Slack Adapter ──verify sig──▶ Normalize to CanonicalMessage
     │
     ▼
PII Firewall ──detect──▶ anonymize ──▶ fail-closed check
     │                                        │
     │ (raw → vault, encrypted)               │ (blocked if risk > threshold)
     ▼                                        ▼
Event Store ◀── ThreadMessageReceived + PIIDetected + PIIAnonymised
     │
     ▼
Workflow Engine ──advance state──▶ route intent
     │                                  │
     ├──▶ Agent Runtime                 ├──▶ Approval Gate (interrupt)
     │       │                          │
     │       ├──▶ Model Router ──▶ LLM  │
     │       ├──▶ Skill Registry        │
     │       └──▶ Sandbox Manager       │
     │               │                  │
     │               ▼                  │
     │         Docker Container         │
     │          (devcontainer)          │
     │               │                  │
     │               ▼                  │
     │         Repo Provider ──▶ GitHub │
     │                                  │
     ▼                                  ▼
Projections ◀── all events ──▶ Slack Adapter (outbound)
```

**Mermaid Diagram:**
```mermaid
sequenceDiagram
    participant U as User (Slack)
    participant SA as Slack Adapter
    participant PII as PII Firewall
    participant V as PII Vault
    participant ES as Event Store
    participant WF as Workflow Engine
    participant AR as Agent Runtime
    participant MR as Model Router
    participant SM as Sandbox Manager
    participant RP as Repo Provider
    participant PR as Projections

    U->>SA: Message in thread
    SA->>SA: Verify signature
    SA->>PII: Canonical message
    PII->>V: Store raw→placeholder mapping
    PII->>PII: Fail-closed check
    PII->>ES: ThreadMessageReceived
    PII->>ES: PIIDetected + PIIAnonymised
    ES->>WF: Event triggers workflow
    WF->>WF: Advance state, route intent
    WF->>AR: Schedule agent step
    AR->>MR: Select model
    MR-->>AR: Provider + model
    AR->>SM: Create sandbox
    SM-->>AR: Sandbox ready
    AR->>RP: Clone repo, create branch
    AR-->>ES: AgentStepCompleted
    ES->>PR: Update projections
    WF->>SA: Send status to Slack
    SA->>U: Block Kit message
```

---

## 2. Data Model

### 2.1 Event Store Schema

**ASCII ERD:**
```
┌─────────────────────────────────┐
│           events                │  (partitioned by occurred_at)
├─────────────────────────────────┤
│ event_id        UUID PK         │
│ stream_id       TEXT NOT NULL    │  -- "thread:{workspace}:{channel}:{ts}"
│ stream_version  BIGINT NOT NULL  │
│ event_type      TEXT NOT NULL    │
│ schema_version  INT NOT NULL     │  -- for upcasting
│ occurred_at     TIMESTAMPTZ      │
│ actor_type      TEXT NOT NULL    │  -- human | agent | system
│ actor_id        TEXT NOT NULL    │
│ correlation_id  UUID NOT NULL    │
│ causation_id    UUID             │
│ thread_ref      JSONB            │  -- {workspace_id, channel_id, thread_ts}
│ payload         JSONB NOT NULL   │
│ payload_hash    TEXT             │  -- SHA-256 of payload
│ prev_hash       TEXT             │  -- hash chain per stream
│ idempotency_key TEXT UNIQUE      │
├─────────────────────────────────┤
│ UNIQUE(stream_id, stream_version)│
└─────────────────────────────────┘
         │
         │ drives
         ▼
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     thread_status_view          │       │     pii_vault                   │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ thread_ref      TEXT PK          │       │ id             UUID PK          │
│ workspace_id    TEXT             │       │ thread_ref     TEXT NOT NULL     │
│ channel_id      TEXT             │       │ placeholder    TEXT NOT NULL     │
│ thread_ts       TEXT             │       │ entity_type    TEXT NOT NULL     │
│ status          TEXT             │       │ encrypted_raw  BYTEA NOT NULL   │
│ current_phase   TEXT             │       │ created_at     TIMESTAMPTZ      │
│ last_event_id   UUID             │       │ revealed_at    TIMESTAMPTZ      │
│ last_event_at   TIMESTAMPTZ      │       │ revealed_by    TEXT             │
│ summary         TEXT             │       ├─────────────────────────────────┤
│ updated_at      TIMESTAMPTZ      │       │ UNIQUE(thread_ref, placeholder) │
└─────────────────────────────────┘       └─────────────────────────────────┘

┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     task_backlog_view           │       │     model_usage_view            │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ task_id         UUID PK          │       │ id             UUID PK          │
│ thread_ref      TEXT NOT NULL     │       │ thread_ref     TEXT             │
│ title           TEXT             │       │ agent_role     TEXT             │
│ status          TEXT             │       │ provider       TEXT             │
│ assigned_agent  TEXT             │       │ model_name     TEXT             │
│ sandbox_job_id  UUID             │       │ input_tokens   INT             │
│ created_at      TIMESTAMPTZ      │       │ output_tokens  INT             │
│ completed_at    TIMESTAMPTZ      │       │ cost_usd       NUMERIC(10,6)   │
│ updated_at      TIMESTAMPTZ      │       │ occurred_at    TIMESTAMPTZ      │
└─────────────────────────────────┘       └─────────────────────────────────┘

┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     skill_registry              │       │     sandbox_jobs_view           │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ skill_id        TEXT PK          │       │ job_id         UUID PK          │
│ version         TEXT NOT NULL     │       │ thread_ref     TEXT NOT NULL     │
│ name            TEXT NOT NULL     │       │ agent_role     TEXT             │
│ input_schema    JSONB            │       │ status         TEXT             │
│ output_schema   JSONB            │       │ container_id   TEXT             │
│ permissions     JSONB            │       │ branch_name    TEXT             │
│ execution_mode  TEXT             │       │ artifacts      JSONB            │
│ enabled         BOOLEAN          │       │ started_at     TIMESTAMPTZ      │
│ registered_at   TIMESTAMPTZ      │       │ completed_at   TIMESTAMPTZ      │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

**Mermaid ERD:**
```mermaid
erDiagram
    EVENTS ||--o{ THREAD_STATUS_VIEW : "projects to"
    EVENTS ||--o{ TASK_BACKLOG_VIEW : "projects to"
    EVENTS ||--o{ MODEL_USAGE_VIEW : "projects to"
    EVENTS ||--o{ SANDBOX_JOBS_VIEW : "projects to"
    EVENTS {
        uuid event_id PK
        text stream_id
        bigint stream_version
        text event_type
        int schema_version
        timestamptz occurred_at
        text actor_type
        text actor_id
        uuid correlation_id
        uuid causation_id
        jsonb thread_ref
        jsonb payload
        text payload_hash
        text prev_hash
        text idempotency_key UK
    }
    PII_VAULT {
        uuid id PK
        text thread_ref
        text placeholder
        text entity_type
        bytea encrypted_raw
        timestamptz created_at
        timestamptz revealed_at
        text revealed_by
    }
    THREAD_STATUS_VIEW {
        text thread_ref PK
        text workspace_id
        text channel_id
        text thread_ts
        text status
        text current_phase
        uuid last_event_id
        text summary
    }
    TASK_BACKLOG_VIEW {
        uuid task_id PK
        text thread_ref
        text title
        text status
        text assigned_agent
    }
    SKILL_REGISTRY {
        text skill_id PK
        text version
        text name
        jsonb input_schema
        jsonb output_schema
        text execution_mode
        boolean enabled
    }
    SANDBOX_JOBS_VIEW {
        uuid job_id PK
        text thread_ref
        text status
        text container_id
        text branch_name
        jsonb artifacts
    }
    MODEL_USAGE_VIEW {
        uuid id PK
        text thread_ref
        text agent_role
        text provider
        text model_name
        int input_tokens
        int output_tokens
    }
```

### 2.2 Migrations

```sql
-- Migration 001: Create event store
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id       TEXT NOT NULL,
    stream_version  BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    schema_version  INT NOT NULL DEFAULT 1,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type      TEXT NOT NULL,
    actor_id        TEXT NOT NULL,
    correlation_id  UUID NOT NULL,
    causation_id    UUID,
    thread_ref      JSONB,
    payload         JSONB NOT NULL,
    payload_hash    TEXT,
    prev_hash       TEXT,
    idempotency_key TEXT,
    UNIQUE (stream_id, stream_version),
    UNIQUE (idempotency_key)
) PARTITION BY RANGE (occurred_at);

-- Create initial partition
CREATE TABLE events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Indexes
CREATE INDEX idx_events_stream ON events (stream_id, stream_version);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_correlation ON events (correlation_id);
CREATE INDEX idx_events_occurred ON events (occurred_at);
CREATE INDEX idx_events_thread_ref ON events USING GIN (thread_ref);

-- Notify trigger for event bridge
CREATE OR REPLACE FUNCTION notify_new_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_event', NEW.event_id::text || ':' || NEW.event_type);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER event_inserted AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION notify_new_event();

-- Rollback
-- DROP TABLE events CASCADE;
-- DROP FUNCTION notify_new_event();
```

```sql
-- Migration 002: Create PII vault
CREATE TABLE pii_vault (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_ref      TEXT NOT NULL,
    placeholder     TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    encrypted_raw   BYTEA NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revealed_at     TIMESTAMPTZ,
    revealed_by     TEXT,
    UNIQUE (thread_ref, placeholder)
);

CREATE INDEX idx_vault_thread ON pii_vault (thread_ref);

-- Rollback
-- DROP TABLE pii_vault;
```

```sql
-- Migration 003: Create projection tables
CREATE TABLE thread_status_view (
    thread_ref      TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    channel_id      TEXT NOT NULL,
    thread_ts       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    current_phase   TEXT,
    last_event_id   UUID,
    last_event_at   TIMESTAMPTZ,
    summary         TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_backlog_view (
    task_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_ref      TEXT NOT NULL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    assigned_agent  TEXT,
    sandbox_job_id  UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_usage_view (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_ref      TEXT,
    agent_role      TEXT,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    input_tokens    INT NOT NULL DEFAULT 0,
    output_tokens   INT NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sandbox_jobs_view (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_ref      TEXT NOT NULL,
    agent_role      TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    container_id    TEXT,
    branch_name     TEXT,
    artifacts       JSONB,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE TABLE skill_registry (
    skill_id        TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    input_schema    JSONB,
    output_schema   JSONB,
    permissions     JSONB,
    execution_mode  TEXT NOT NULL DEFAULT 'inline',
    enabled         BOOLEAN NOT NULL DEFAULT true,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Rollback
-- DROP TABLE thread_status_view, task_backlog_view, model_usage_view,
--            sandbox_jobs_view, skill_registry;
```

---

## 3. Implementation Phases

### Phase Overview

| Phase | Description | Parallel With | Dependencies |
|-------|-------------|---------------|--------------|
| 1 | Project Skeleton & Tooling | - | None |
| 2 | Contracts & Domain Types | - | Phase 1 |
| 3 | Event Store | - | Phase 2 |
| 4 | PII Firewall & Vault | Phase 5 | Phase 2 |
| 5 | Configuration & Observability | Phase 4 | Phase 2 |
| 6 | Slack Channel Adapter | - | Phases 3, 4 |
| 7 | Workflow Engine (LangGraph) | - | Phases 3, 6 |
| 8 | Agent Runtime & Model Router | - | Phase 7 |
| 9 | Skill Registry | Phase 10 | Phase 8 |
| 10 | Sandbox Manager | Phase 9 | Phase 8 |
| 11 | Repo Provider (GitHub) | - | Phase 10 |
| 12 | Projections & Read Models | - | Phase 3 (can start early, finalize after 8) |
| 13 | API Layer & FastAPI Wiring | - | Phases 6-12 |
| 14 | Docker Compose & Local Dev | - | Phase 13 |
| 15 | Integration Tests & E2E | - | Phase 14 |
| 16 | Documentation & CI/CD | - | Phase 15 |

---

### Phase 1: Project Skeleton & Tooling

**Objective:** Initialize the Python project with uv, directory structure, linting, and test infrastructure.
**Can run in parallel with:** None

#### Step 1.1: Initialize Project with uv

**Files:**
- `pyproject.toml` (new)
- `.python-version` (new)
- `README.md` (new)
- `.gitignore` (new)

**After:**
```toml
# pyproject.toml
[project]
name = "lintel"
version = "0.1.0"
description = "Open Source AI Collaboration Infrastructure"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "asyncpg>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "langgraph>=0.3",
    "langgraph-checkpoint-postgres>=2.0",
    "presidio-analyzer>=2.2",
    "presidio-anonymizer>=2.2",
    "litellm>=1.55",
    "slack-bolt>=1.21",
    "slack-sdk>=3.33",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "structlog>=24.4",
    "httpx>=0.28",
    "tenacity>=9.0",
    "opentelemetry-sdk>=1.29",
    "opentelemetry-exporter-otlp>=1.29",
    "cryptography>=44.0",
    "nats-py>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "testcontainers[postgres,nats]>=4.9",
    "ruff>=0.8",
    "mypy>=1.13",
    "pre-commit>=4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/lintel"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "A", "SIM", "TCH", "RUF"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

#### Step 1.2: Create Directory Structure

**Files:**
```
src/lintel/__init__.py (new)
src/lintel/contracts/__init__.py (new)
src/lintel/domain/__init__.py (new)
src/lintel/infrastructure/__init__.py (new)
src/lintel/infrastructure/event_store/__init__.py (new)
src/lintel/infrastructure/channels/__init__.py (new)
src/lintel/infrastructure/channels/slack/__init__.py (new)
src/lintel/infrastructure/pii/__init__.py (new)
src/lintel/infrastructure/vault/__init__.py (new)
src/lintel/infrastructure/models/__init__.py (new)
src/lintel/infrastructure/repos/__init__.py (new)
src/lintel/infrastructure/sandbox/__init__.py (new)
src/lintel/infrastructure/observability/__init__.py (new)
src/lintel/workflows/__init__.py (new)
src/lintel/workflows/nodes/__init__.py (new)
src/lintel/agents/__init__.py (new)
src/lintel/skills/__init__.py (new)
src/lintel/projections/__init__.py (new)
src/lintel/api/__init__.py (new)
src/lintel/api/routes/__init__.py (new)
src/lintel/api/middleware/__init__.py (new)
tests/__init__.py (new)
tests/unit/__init__.py (new)
tests/integration/__init__.py (new)
tests/e2e/__init__.py (new)
tests/conftest.py (new)
migrations/ (new directory)
ops/ (new directory)
```

#### Step 1.3: Configure Linting and Pre-commit

**Files:**
- `.pre-commit-config.yaml` (new)

**After:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.10]
```

#### Step 1.4: Create Taskfile

**Files:**
- `Taskfile.yaml` (new)

**After:**
```yaml
# Taskfile.yaml
version: "3"

tasks:
  install:
    cmds:
      - uv sync --all-extras

  test:
    cmds:
      - uv run pytest {{.CLI_ARGS}}

  test-unit:
    cmds:
      - uv run pytest tests/unit -v

  test-integration:
    cmds:
      - uv run pytest tests/integration -v

  test-e2e:
    cmds:
      - uv run pytest tests/e2e -v

  lint:
    cmds:
      - uv run ruff check src/ tests/
      - uv run ruff format --check src/ tests/

  typecheck:
    cmds:
      - uv run mypy src/lintel/

  format:
    cmds:
      - uv run ruff format src/ tests/
      - uv run ruff check --fix src/ tests/

  serve:
    cmds:
      - uv run uvicorn lintel.api.app:app --reload --port 8000

  migrate:
    cmds:
      - uv run python -m lintel.infrastructure.event_store.migrate

  all:
    cmds:
      - task: lint
      - task: typecheck
      - task: test
```

**Test Strategy:**
- Verify `uv sync` completes without errors
- Verify `task lint` runs cleanly
- Verify `task typecheck` runs cleanly
- Verify `task test` discovers test directory

**Validation:**
```bash
uv sync --all-extras
task lint
task typecheck
task test-unit
```

---

### Phase 2: Contracts & Domain Types

**Objective:** Define all shared types, event envelope, event types, command schemas, and Protocol interfaces. This is the shared kernel that all modules depend on.
**Can run in parallel with:** None (foundation for everything)

#### Step 2.1: Core Types

**Files:**
- `src/lintel/contracts/types.py` (new)
- `tests/unit/contracts/__init__.py` (new)
- `tests/unit/contracts/test_types.py` (new)

**After:**
```python
# src/lintel/contracts/types.py
"""Core domain types for Lintel. Immutable, no I/O dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType
from uuid import UUID


@dataclass(frozen=True)
class ThreadRef:
    """Canonical identifier for a workflow instance (Slack thread)."""
    workspace_id: str
    channel_id: str
    thread_ts: str

    @property
    def stream_id(self) -> str:
        return f"thread:{self.workspace_id}:{self.channel_id}:{self.thread_ts}"

    def __str__(self) -> str:
        return self.stream_id


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class AgentRole(StrEnum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    PM = "pm"
    DESIGNER = "designer"
    SUMMARIZER = "summarizer"


class WorkflowPhase(StrEnum):
    INGESTING = "ingesting"
    PLANNING = "planning"
    AWAITING_SPEC_APPROVAL = "awaiting_spec_approval"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    MERGING = "merging"
    CLOSED = "closed"


class SandboxStatus(StrEnum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


class SkillExecutionMode(StrEnum):
    INLINE = "inline"
    ASYNC_JOB = "async_job"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class ModelPolicy:
    """Policy for model selection per agent role."""
    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


CorrelationId = NewType("CorrelationId", UUID)
EventId = NewType("EventId", UUID)
```

#### Step 2.2: Event Envelope and Event Types

**Files:**
- `src/lintel/contracts/events.py` (new)
- `tests/unit/contracts/test_events.py` (new)

**After:**
```python
# src/lintel/contracts/events.py
"""Immutable event types for Lintel's event-sourced architecture.

Events are past-tense facts. They are never rejected or modified.
Every event carries a schema_version for upcasting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from lintel.contracts.types import ActorType, ThreadRef


@dataclass(frozen=True)
class EventEnvelope:
    """Shared envelope for all domain events."""
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    schema_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = ""
    thread_ref: ThreadRef | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


# --- Channel & Ingestion Events ---

@dataclass(frozen=True)
class ThreadMessageReceived(EventEnvelope):
    event_type: str = "ThreadMessageReceived"
    # payload: {sanitized_text, sender_id, sender_name, channel_type}


@dataclass(frozen=True)
class PIIDetected(EventEnvelope):
    event_type: str = "PIIDetected"
    # payload: {entities: [{type, start, end, score}], total_count}


@dataclass(frozen=True)
class PIIAnonymised(EventEnvelope):
    event_type: str = "PIIAnonymised"
    # payload: {placeholder_count, placeholders: [str]}


@dataclass(frozen=True)
class PIIResidualRiskBlocked(EventEnvelope):
    event_type: str = "PIIResidualRiskBlocked"
    # payload: {risk_score, threshold, reason}


# --- Workflow Events ---

@dataclass(frozen=True)
class IntentRouted(EventEnvelope):
    event_type: str = "IntentRouted"
    # payload: {intent, workflow_type, confidence}


@dataclass(frozen=True)
class WorkflowStarted(EventEnvelope):
    event_type: str = "WorkflowStarted"
    # payload: {workflow_type, initial_phase}


@dataclass(frozen=True)
class WorkflowAdvanced(EventEnvelope):
    event_type: str = "WorkflowAdvanced"
    # payload: {from_phase, to_phase, reason}


# --- Agent Events ---

@dataclass(frozen=True)
class AgentStepScheduled(EventEnvelope):
    event_type: str = "AgentStepScheduled"
    # payload: {agent_role, step_name, context_summary}


@dataclass(frozen=True)
class AgentStepStarted(EventEnvelope):
    event_type: str = "AgentStepStarted"
    # payload: {agent_role, step_name}


@dataclass(frozen=True)
class AgentStepCompleted(EventEnvelope):
    event_type: str = "AgentStepCompleted"
    # payload: {agent_role, step_name, output_summary}


@dataclass(frozen=True)
class ModelSelected(EventEnvelope):
    event_type: str = "ModelSelected"
    # payload: {agent_role, provider, model_name, reason}


@dataclass(frozen=True)
class ModelCallCompleted(EventEnvelope):
    event_type: str = "ModelCallCompleted"
    # payload: {provider, model, input_tokens, output_tokens, latency_ms, cost_usd}


# --- Sandbox Events ---

@dataclass(frozen=True)
class SandboxJobScheduled(EventEnvelope):
    event_type: str = "SandboxJobScheduled"
    # payload: {job_id, agent_role, repo_url, base_sha}


@dataclass(frozen=True)
class SandboxCreated(EventEnvelope):
    event_type: str = "SandboxCreated"
    # payload: {job_id, container_id, image}


@dataclass(frozen=True)
class SandboxArtifactsCollected(EventEnvelope):
    event_type: str = "SandboxArtifactsCollected"
    # payload: {job_id, artifacts: {logs, diffs, test_results}}


@dataclass(frozen=True)
class SandboxDestroyed(EventEnvelope):
    event_type: str = "SandboxDestroyed"
    # payload: {job_id, reason}


# --- Repo Events ---

@dataclass(frozen=True)
class BranchCreated(EventEnvelope):
    event_type: str = "BranchCreated"
    # payload: {repo, branch_name, base_sha}


@dataclass(frozen=True)
class PRCreated(EventEnvelope):
    event_type: str = "PRCreated"
    # payload: {repo, pr_number, pr_url, title}


@dataclass(frozen=True)
class HumanApprovalGranted(EventEnvelope):
    event_type: str = "HumanApprovalGranted"
    # payload: {gate_type, approver_id, approver_name}


@dataclass(frozen=True)
class HumanApprovalRejected(EventEnvelope):
    event_type: str = "HumanApprovalRejected"
    # payload: {gate_type, rejector_id, reason}


# --- Security Events ---

@dataclass(frozen=True)
class VaultRevealRequested(EventEnvelope):
    event_type: str = "VaultRevealRequested"
    # payload: {placeholder, requester_id, reason}


@dataclass(frozen=True)
class VaultRevealGranted(EventEnvelope):
    event_type: str = "VaultRevealGranted"
    # payload: {placeholder, approver_id}


@dataclass(frozen=True)
class PolicyDecisionRecorded(EventEnvelope):
    event_type: str = "PolicyDecisionRecorded"
    # payload: {decision, policy_name, subject, resource, reason}


# --- Event Registry ---

EVENT_TYPE_MAP: dict[str, type[EventEnvelope]] = {
    cls.event_type: cls  # type: ignore[attr-defined]
    for cls in [
        ThreadMessageReceived, PIIDetected, PIIAnonymised, PIIResidualRiskBlocked,
        IntentRouted, WorkflowStarted, WorkflowAdvanced,
        AgentStepScheduled, AgentStepStarted, AgentStepCompleted,
        ModelSelected, ModelCallCompleted,
        SandboxJobScheduled, SandboxCreated, SandboxArtifactsCollected, SandboxDestroyed,
        BranchCreated, PRCreated, HumanApprovalGranted, HumanApprovalRejected,
        VaultRevealRequested, VaultRevealGranted, PolicyDecisionRecorded,
    ]
}


def deserialize_event(event_type: str, data: dict[str, Any]) -> EventEnvelope:
    """Deserialize an event from stored data. Raises KeyError for unknown types."""
    cls = EVENT_TYPE_MAP[event_type]
    return cls(**data)
```

#### Step 2.3: Protocol Interfaces

**Files:**
- `src/lintel/contracts/protocols.py` (new)
- `tests/unit/contracts/test_protocols.py` (new)

**After:**
```python
# src/lintel/contracts/protocols.py
"""Protocol interfaces defining service boundaries.

Domain code depends on these abstractions. Infrastructure provides implementations.
No concrete imports from infrastructure in this file.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence
from uuid import UUID

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


class EventStore(Protocol):
    """Append-only event persistence with optimistic concurrency."""

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None: ...

    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[EventEnvelope]: ...

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]: ...

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]: ...


class DeidentifyResult(Protocol):
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class Deidentifier(Protocol):
    """PII detection and anonymization pipeline."""

    async def analyze_and_anonymize(
        self,
        text: str,
        thread_ref: ThreadRef,
        language: str = "en",
    ) -> DeidentifyResult: ...


class PIIVault(Protocol):
    """Encrypted storage for PII placeholder mappings."""

    async def store_mapping(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        entity_type: str,
        raw_value: str,
    ) -> None: ...

    async def reveal(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        revealer_id: str,
    ) -> str: ...


class ChannelAdapter(Protocol):
    """Pluggable channel interface. Slack is the first implementation."""

    async def send_message(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    async def send_approval_request(
        self,
        channel_id: str,
        thread_ts: str,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]: ...


class ModelRouter(Protocol):
    """Selects model provider based on agent role and policy."""

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy: ...

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


class CommandResult(Protocol):
    exit_code: int
    stdout: str
    stderr: str


class SandboxManager(Protocol):
    """Manages isolated sandbox containers for code execution."""

    async def create_sandbox(
        self,
        job_id: UUID,
        repo_url: str,
        base_sha: str,
        branch_name: str,
        devcontainer_config: dict[str, Any] | None = None,
    ) -> str: ...

    async def execute_command(
        self,
        container_id: str,
        command: str,
        timeout: int = 300,
    ) -> CommandResult: ...

    async def collect_artifacts(
        self,
        container_id: str,
    ) -> dict[str, Any]: ...

    async def destroy_sandbox(
        self,
        container_id: str,
    ) -> None: ...


class RepoProvider(Protocol):
    """Git and PR operations for a repository host."""

    async def clone_repo(
        self,
        repo_url: str,
        branch: str,
        target_dir: str,
    ) -> None: ...

    async def create_branch(
        self,
        repo_url: str,
        branch_name: str,
        base_sha: str,
    ) -> None: ...

    async def create_pr(
        self,
        repo_url: str,
        branch_name: str,
        title: str,
        body: str,
    ) -> dict[str, Any]: ...


class SkillRegistry(Protocol):
    """Dynamic skill registration and discovery."""

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
    ) -> None: ...

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def list_skills(self) -> list[dict[str, Any]]: ...
```

#### Step 2.4: Command Schemas

**Files:**
- `src/lintel/contracts/commands.py` (new)
- `tests/unit/contracts/test_commands.py` (new)

**After:**
```python
# src/lintel/contracts/commands.py
"""Command schemas express intent. Commands are imperative and may fail."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from lintel.contracts.types import AgentRole, ThreadRef


@dataclass(frozen=True)
class ProcessIncomingMessage:
    thread_ref: ThreadRef
    raw_text: str
    sender_id: str
    sender_name: str
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class StartWorkflow:
    thread_ref: ThreadRef
    workflow_type: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ScheduleAgentStep:
    thread_ref: ThreadRef
    agent_role: AgentRole
    step_name: str
    context: dict = field(default_factory=dict)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ScheduleSandboxJob:
    thread_ref: ThreadRef
    agent_role: AgentRole
    repo_url: str
    base_sha: str
    commands: list[str] = field(default_factory=list)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class GrantApproval:
    thread_ref: ThreadRef
    gate_type: str
    approver_id: str
    approver_name: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RejectApproval:
    thread_ref: ThreadRef
    gate_type: str
    rejector_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RevealPII:
    thread_ref: ThreadRef
    placeholder: str
    requester_id: str
    reason: str
    correlation_id: UUID = field(default_factory=uuid4)
```

**Test Strategy:**
- Unit: Verify all types are frozen/immutable
- Unit: Verify EVENT_TYPE_MAP completeness
- Unit: Verify deserialize_event round-trips
- Unit: Verify ThreadRef.stream_id format

**Validation:**
```bash
task typecheck
task test -- tests/unit/contracts/
```

---

### Phase 3: Event Store

**Objective:** Implement the Postgres-based append-only event store with optimistic concurrency, hash chaining, and LISTEN/NOTIFY bridge.
**Can run in parallel with:** None (critical path)

#### Step 3.1: Postgres Event Store Implementation

**Files:**
- `src/lintel/infrastructure/event_store/postgres.py` (new)
- `src/lintel/infrastructure/event_store/serialization.py` (new)
- `tests/integration/test_event_store.py` (new)

**After:**
```python
# src/lintel/infrastructure/event_store/postgres.py
"""Postgres append-only event store with optimistic concurrency and hash chaining."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence
from uuid import UUID

import asyncpg
import structlog

from lintel.contracts.events import EVENT_TYPE_MAP, EventEnvelope

logger = structlog.get_logger()


class PostgresEventStore:
    """Implements EventStore protocol with Postgres backend."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(
        self,
        stream_id: str,
        events: Sequence[EventEnvelope],
        expected_version: int | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if expected_version is not None:
                    current = await conn.fetchval(
                        "SELECT COALESCE(MAX(stream_version), -1) "
                        "FROM events WHERE stream_id = $1",
                        stream_id,
                    )
                    if current != expected_version:
                        raise OptimisticConcurrencyError(
                            f"Expected version {expected_version}, got {current}"
                        )

                prev_hash = await conn.fetchval(
                    "SELECT payload_hash FROM events WHERE stream_id = $1 "
                    "ORDER BY stream_version DESC LIMIT 1",
                    stream_id,
                )

                base_version = expected_version if expected_version is not None else (
                    await conn.fetchval(
                        "SELECT COALESCE(MAX(stream_version), -1) "
                        "FROM events WHERE stream_id = $1",
                        stream_id,
                    )
                )

                for i, event in enumerate(events):
                    version = base_version + 1 + i
                    payload_json = json.dumps(
                        event.payload, sort_keys=True, default=str
                    )
                    payload_hash = hashlib.sha256(
                        payload_json.encode()
                    ).hexdigest()

                    thread_ref_json = None
                    if event.thread_ref:
                        thread_ref_json = json.dumps({
                            "workspace_id": event.thread_ref.workspace_id,
                            "channel_id": event.thread_ref.channel_id,
                            "thread_ts": event.thread_ref.thread_ts,
                        })

                    await conn.execute(
                        """
                        INSERT INTO events (
                            event_id, stream_id, stream_version, event_type,
                            schema_version, occurred_at, actor_type, actor_id,
                            correlation_id, causation_id, thread_ref,
                            payload, payload_hash, prev_hash, idempotency_key
                        ) VALUES (
                            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                            $12::jsonb,$13,$14,$15
                        )
                        """,
                        event.event_id, stream_id, version, event.event_type,
                        event.schema_version, event.occurred_at,
                        event.actor_type.value, event.actor_id,
                        event.correlation_id, event.causation_id,
                        thread_ref_json, payload_json,
                        payload_hash, prev_hash, event.idempotency_key,
                    )
                    prev_hash = payload_hash

                logger.info(
                    "events_appended",
                    stream_id=stream_id,
                    count=len(events),
                    new_version=base_version + len(events),
                )

    async def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events "
                "WHERE stream_id = $1 AND stream_version >= $2 "
                "ORDER BY stream_version",
                stream_id, from_version,
            )
            return [_row_to_event(row) for row in rows]

    async def read_all(
        self,
        from_position: int = 0,
        limit: int = 1000,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events ORDER BY occurred_at, stream_version "
                "OFFSET $1 LIMIT $2",
                from_position, limit,
            )
            return [_row_to_event(row) for row in rows]

    async def read_by_correlation(
        self,
        correlation_id: UUID,
    ) -> list[EventEnvelope]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE correlation_id = $1 "
                "ORDER BY occurred_at",
                correlation_id,
            )
            return [_row_to_event(row) for row in rows]


class OptimisticConcurrencyError(Exception):
    pass


def _row_to_event(row: asyncpg.Record) -> EventEnvelope:
    """Deserialize a database row to an EventEnvelope."""
    from lintel.contracts.types import ActorType, ThreadRef

    thread_ref = None
    if row["thread_ref"]:
        tr = (
            json.loads(row["thread_ref"])
            if isinstance(row["thread_ref"], str)
            else row["thread_ref"]
        )
        thread_ref = ThreadRef(
            workspace_id=tr["workspace_id"],
            channel_id=tr["channel_id"],
            thread_ts=tr["thread_ts"],
        )

    payload = (
        json.loads(row["payload"])
        if isinstance(row["payload"], str)
        else row["payload"]
    )

    cls = EVENT_TYPE_MAP.get(row["event_type"], EventEnvelope)
    return cls(
        event_id=row["event_id"],
        event_type=row["event_type"],
        schema_version=row["schema_version"],
        occurred_at=row["occurred_at"],
        actor_type=ActorType(row["actor_type"]),
        actor_id=row["actor_id"],
        thread_ref=thread_ref,
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        payload=payload,
        idempotency_key=row.get("idempotency_key"),
    )
```

#### Step 3.2: Migration Runner

**Files:**
- `src/lintel/infrastructure/event_store/migrate.py` (new)
- `migrations/001_create_event_store.sql` (new)
- `migrations/002_create_pii_vault.sql` (new)
- `migrations/003_create_projections.sql` (new)

The SQL content for each migration file is defined in Section 2.2 above.

#### Step 3.3: Event Store Tests

**Files:**
- `tests/integration/test_event_store.py` (new)
- `tests/conftest.py` (modify)

**After:**
```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")
```

```python
# tests/integration/test_event_store.py
import pytest
import asyncpg
from uuid import uuid4

from lintel.contracts.events import ThreadMessageReceived
from lintel.contracts.types import ActorType, ThreadRef
from lintel.infrastructure.event_store.postgres import (
    PostgresEventStore,
    OptimisticConcurrencyError,
)


@pytest.fixture
async def event_store(postgres_url):
    pool = await asyncpg.create_pool(postgres_url)
    async with pool.acquire() as conn:
        with open("migrations/001_create_event_store.sql") as f:
            await conn.execute(f.read())
    store = PostgresEventStore(pool)
    yield store
    await pool.close()


async def test_append_and_read_stream(event_store):
    thread_ref = ThreadRef("W1", "C1", "1234.5678")
    event = ThreadMessageReceived(
        actor_type=ActorType.HUMAN,
        actor_id="U123",
        thread_ref=thread_ref,
        correlation_id=uuid4(),
        payload={
            "sanitized_text": "Hello world",
            "sender_id": "U123",
        },
    )

    await event_store.append(thread_ref.stream_id, [event])
    events = await event_store.read_stream(thread_ref.stream_id)

    assert len(events) == 1
    assert events[0].event_type == "ThreadMessageReceived"
    assert events[0].payload["sanitized_text"] == "Hello world"


async def test_optimistic_concurrency(event_store):
    stream_id = f"test:{uuid4()}"
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "test"},
    )

    await event_store.append(stream_id, [event], expected_version=-1)

    with pytest.raises(OptimisticConcurrencyError):
        await event_store.append(stream_id, [event], expected_version=-1)


async def test_hash_chaining(event_store):
    stream_id = f"test:{uuid4()}"
    events = [
        ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            correlation_id=uuid4(),
            payload={"sanitized_text": f"msg {i}"},
        )
        for i in range(3)
    ]

    await event_store.append(stream_id, events)
    stored = await event_store.read_stream(stream_id)
    assert len(stored) == 3


async def test_idempotency(event_store):
    stream_id = f"test:{uuid4()}"
    key = str(uuid4())
    event = ThreadMessageReceived(
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        correlation_id=uuid4(),
        payload={"sanitized_text": "idempotent"},
        idempotency_key=key,
    )

    await event_store.append(stream_id, [event])
    with pytest.raises(Exception):
        await event_store.append(stream_id, [event])
```

**Test Strategy:**
- Integration: Real Postgres via testcontainers
- Test: append, read, optimistic concurrency, hash chain, idempotency, correlation query

**Validation:**
```bash
task test -- tests/integration/test_event_store.py
```

---

### Phase 4: PII Firewall & Vault

**Objective:** Implement Presidio-based PII detection, anonymization with stable per-thread placeholders, fail-closed behavior, and encrypted PII vault.
**Can run in parallel with:** Phase 5

#### Step 4.1: Presidio PII Firewall

**Files:**
- `src/lintel/infrastructure/pii/presidio_firewall.py` (new)
- `src/lintel/infrastructure/pii/placeholder_manager.py` (new)
- `tests/unit/infrastructure/__init__.py` (new)
- `tests/unit/infrastructure/test_pii_firewall.py` (new)

**After:**
```python
# src/lintel/infrastructure/pii/presidio_firewall.py
"""Presidio-based PII detection and anonymization. Fail-closed."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from lintel.contracts.types import ThreadRef
from lintel.infrastructure.pii.placeholder_manager import PlaceholderManager

logger = structlog.get_logger()

DEFAULT_RISK_THRESHOLD = 0.6


@dataclass(frozen=True)
class DeidentifyResultImpl:
    sanitized_text: str
    entities_detected: list[dict[str, Any]]
    placeholder_count: int
    is_blocked: bool
    risk_score: float


class PresidioFirewall:
    """Implements Deidentifier protocol with Microsoft Presidio."""

    def __init__(
        self,
        vault: Any,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
    ) -> None:
        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()
        self._vault = vault
        self._risk_threshold = risk_threshold
        self._placeholder_mgr = PlaceholderManager()

    async def analyze_and_anonymize(
        self,
        text: str,
        thread_ref: ThreadRef,
        language: str = "en",
    ) -> DeidentifyResultImpl:
        # Presidio is sync -- wrap in thread
        results: list[RecognizerResult] = await asyncio.to_thread(
            self._analyzer.analyze,
            text=text,
            language=language,
            entities=None,
        )

        entities = [
            {
                "type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": r.score,
            }
            for r in results
        ]

        if not results:
            return DeidentifyResultImpl(
                sanitized_text=text,
                entities_detected=[],
                placeholder_count=0,
                is_blocked=False,
                risk_score=0.0,
            )

        risk_score = max(r.score for r in results)

        # Fail-closed: block if risk is above threshold
        if risk_score > self._risk_threshold:
            logger.warning(
                "pii_blocked",
                thread_ref=str(thread_ref),
                risk_score=risk_score,
                entity_count=len(results),
            )
            return DeidentifyResultImpl(
                sanitized_text="[BLOCKED: PII risk too high]",
                entities_detected=entities,
                placeholder_count=0,
                is_blocked=True,
                risk_score=risk_score,
            )

        # Anonymize with stable per-thread placeholders
        sanitized = text
        placeholder_count = 0

        # Process from end to preserve offsets
        for result in sorted(results, key=lambda r: r.start, reverse=True):
            raw_value = text[result.start:result.end]
            placeholder = self._placeholder_mgr.get_or_create(
                thread_ref, result.entity_type, raw_value,
            )
            sanitized = (
                sanitized[:result.start] + placeholder + sanitized[result.end:]
            )
            placeholder_count += 1

            await self._vault.store_mapping(
                thread_ref=thread_ref,
                placeholder=placeholder,
                entity_type=result.entity_type,
                raw_value=raw_value,
            )

        logger.info(
            "pii_anonymized",
            thread_ref=str(thread_ref),
            entity_count=len(results),
            placeholder_count=placeholder_count,
        )

        return DeidentifyResultImpl(
            sanitized_text=sanitized,
            entities_detected=entities,
            placeholder_count=placeholder_count,
            is_blocked=False,
            risk_score=risk_score,
        )
```

```python
# src/lintel/infrastructure/pii/placeholder_manager.py
"""Stable placeholder generation per thread."""

from __future__ import annotations

from lintel.contracts.types import ThreadRef


class PlaceholderManager:
    """Generates stable placeholders like <PERSON_1>, <EMAIL_2> per thread."""

    def __init__(self) -> None:
        self._mappings: dict[str, dict[tuple[str, str], str]] = {}
        self._counters: dict[str, dict[str, int]] = {}

    def get_or_create(
        self,
        thread_ref: ThreadRef,
        entity_type: str,
        raw_value: str,
    ) -> str:
        stream = thread_ref.stream_id
        key = (entity_type, raw_value)

        if stream not in self._mappings:
            self._mappings[stream] = {}
            self._counters[stream] = {}

        if key in self._mappings[stream]:
            return self._mappings[stream][key]

        if entity_type not in self._counters[stream]:
            self._counters[stream][entity_type] = 0

        self._counters[stream][entity_type] += 1
        placeholder = f"<{entity_type}_{self._counters[stream][entity_type]}>"
        self._mappings[stream][key] = placeholder
        return placeholder
```

#### Step 4.2: Encrypted PII Vault

**Files:**
- `src/lintel/infrastructure/vault/postgres_vault.py` (new)
- `tests/integration/test_pii_vault.py` (new)

**After:**
```python
# src/lintel/infrastructure/vault/postgres_vault.py
"""Encrypted PII vault. Human-only reveal with audit."""

from __future__ import annotations

import asyncpg
import structlog
from cryptography.fernet import Fernet

from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()


class PostgresPIIVault:
    """Implements PIIVault protocol with Postgres + Fernet encryption."""

    def __init__(self, pool: asyncpg.Pool, encryption_key: str) -> None:
        self._pool = pool
        self._fernet = Fernet(encryption_key.encode())

    async def store_mapping(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        entity_type: str,
        raw_value: str,
    ) -> None:
        encrypted = self._fernet.encrypt(raw_value.encode())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pii_vault
                    (thread_ref, placeholder, entity_type, encrypted_raw)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (thread_ref, placeholder) DO NOTHING
                """,
                thread_ref.stream_id,
                placeholder,
                entity_type,
                encrypted,
            )

    async def reveal(
        self,
        thread_ref: ThreadRef,
        placeholder: str,
        revealer_id: str,
    ) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT encrypted_raw FROM pii_vault "
                "WHERE thread_ref = $1 AND placeholder = $2",
                thread_ref.stream_id, placeholder,
            )
            if not row:
                raise ValueError(f"No vault entry for {placeholder}")

            await conn.execute(
                "UPDATE pii_vault SET revealed_at = now(), revealed_by = $1 "
                "WHERE thread_ref = $2 AND placeholder = $3",
                revealer_id, thread_ref.stream_id, placeholder,
            )

        logger.warning(
            "pii_revealed",
            thread_ref=str(thread_ref),
            placeholder=placeholder,
            revealer_id=revealer_id,
        )
        return self._fernet.decrypt(row["encrypted_raw"]).decode()
```

**Test Strategy:**
- Unit: PlaceholderManager stability (same input returns same placeholder)
- Unit: Fail-closed threshold logic
- Integration: Full Presidio pipeline with testcontainers Postgres for vault
- Test: PII in code comments, variable names, mixed content

**Validation:**
```bash
task test -- tests/unit/infrastructure/test_pii_firewall.py
task test -- tests/integration/test_pii_vault.py
```

---

### Phase 5: Configuration & Observability

**Objective:** Typed configuration with pydantic-settings, structured logging with structlog, and OpenTelemetry tracing setup.
**Can run in parallel with:** Phase 4

#### Step 5.1: Configuration

**Files:**
- `src/lintel/config.py` (new)
- `tests/unit/test_config.py` (new)

**After:**
```python
# src/lintel/config.py
"""Typed configuration via pydantic-settings. Loaded from env vars."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_DB_"}

    dsn: str = "postgresql://lintel:lintel@localhost:5432/lintel"
    pool_min: int = 5
    pool_max: int = 20


class NATSSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_NATS_"}

    url: str = "nats://localhost:4222"
    enabled: bool = False


class SlackSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_SLACK_"}

    bot_token: str = ""
    signing_secret: str = ""
    app_token: str = ""


class PIISettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_PII_"}

    risk_threshold: float = 0.6
    vault_encryption_key: str = ""


class ModelSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_MODEL_"}

    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    fallback_provider: str = "ollama"
    fallback_model: str = "llama3.1:8b"


class SandboxSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_SANDBOX_"}

    docker_host: str = "unix:///var/run/docker.sock"
    max_cpu: str = "2"
    max_memory: str = "4g"
    timeout_seconds: int = 1800
    network_mode: str = "none"


class Settings(BaseSettings):
    """Root settings aggregating all subsystems."""

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    nats: NATSSettings = Field(default_factory=NATSSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    pii: PIISettings = Field(default_factory=PIISettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)

    log_level: str = "INFO"
    log_format: str = "json"
    otel_endpoint: str = ""
    environment: str = "development"
```

#### Step 5.2: Structured Logging & Correlation

**Files:**
- `src/lintel/infrastructure/observability/logging.py` (new)
- `src/lintel/infrastructure/observability/tracing.py` (new)
- `src/lintel/infrastructure/observability/correlation.py` (new)

**After:**
```python
# src/lintel/infrastructure/observability/correlation.py
"""Correlation ID propagation via contextvars."""

from __future__ import annotations

import contextvars
from uuid import UUID, uuid4

correlation_id_var: contextvars.ContextVar[UUID] = contextvars.ContextVar(
    "correlation_id", default=uuid4()
)


def get_correlation_id() -> UUID:
    return correlation_id_var.get()


def set_correlation_id(cid: UUID) -> contextvars.Token[UUID]:
    return correlation_id_var.set(cid)
```

```python
# src/lintel/infrastructure/observability/logging.py
"""Structured logging configuration with structlog."""

from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog with JSON output and correlation ID merging."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

```python
# src/lintel/infrastructure/observability/tracing.py
"""OpenTelemetry tracing setup."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)


def configure_tracing(otel_endpoint: str = "") -> trace.Tracer:
    """Configure OpenTelemetry with optional OTLP exporter."""
    provider = TracerProvider()

    if otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer("lintel")
```

**Test Strategy:**
- Unit: Settings loading from env vars
- Unit: Correlation ID propagation across async boundaries

**Validation:**
```bash
task test -- tests/unit/test_config.py
task typecheck
```

---

### Phase 6: Slack Channel Adapter

**Objective:** Implement the Slack adapter behind the ChannelAdapter protocol using slack-bolt, with event translation, approval gate buttons, and Block Kit formatting.
**Dependencies:** Phases 3, 4

#### Step 6.1: Event Translator

**Files:**
- `src/lintel/infrastructure/channels/slack/event_translator.py` (new)
- `tests/unit/channels/__init__.py` (new)
- `tests/unit/channels/slack/__init__.py` (new)
- `tests/unit/channels/slack/test_event_translator.py` (new)

**After:**
```python
# src/lintel/infrastructure/channels/slack/event_translator.py
"""Translate Slack events to Lintel domain commands."""

from __future__ import annotations

from lintel.contracts.commands import (
    GrantApproval,
    ProcessIncomingMessage,
    RejectApproval,
)
from lintel.contracts.types import ThreadRef


def translate_message_event(
    event: dict,
) -> ProcessIncomingMessage | None:
    """Translate a Slack message event to a ProcessIncomingMessage command."""
    if event.get("bot_id") or event.get("subtype"):
        return None

    thread_ts = event.get("thread_ts", event.get("ts", ""))
    channel_id = event.get("channel", "")
    team_id = event.get("team", "")

    if not all([thread_ts, channel_id, team_id]):
        return None

    return ProcessIncomingMessage(
        thread_ref=ThreadRef(
            workspace_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
        ),
        raw_text=event.get("text", ""),
        sender_id=event.get("user", ""),
        sender_name="",
    )


def translate_approval_action(
    body: dict,
) -> GrantApproval | RejectApproval | None:
    """Translate a Slack interactive action to an approval command."""
    actions = body.get("actions", [])
    if not actions:
        return None

    action = actions[0]
    action_id = action.get("action_id", "")
    user = body.get("user", {})

    # Parse action_id: "approve:{gate_type}:{thread_ref}"
    parts = action_id.split(":", 2)
    if len(parts) < 3:
        return None

    decision, gate_type, thread_ref_str = parts
    ref_parts = thread_ref_str.split(":")
    if len(ref_parts) < 4:
        return None

    thread_ref = ThreadRef(
        workspace_id=ref_parts[1],
        channel_id=ref_parts[2],
        thread_ts=ref_parts[3],
    )

    if decision == "approve":
        return GrantApproval(
            thread_ref=thread_ref,
            gate_type=gate_type,
            approver_id=user.get("id", ""),
            approver_name=user.get("name", ""),
        )
    elif decision == "reject":
        return RejectApproval(
            thread_ref=thread_ref,
            gate_type=gate_type,
            rejector_id=user.get("id", ""),
            reason=action.get("value", ""),
        )
    return None
```

#### Step 6.2: Slack Adapter Implementation

**Files:**
- `src/lintel/infrastructure/channels/slack/adapter.py` (new)
- `src/lintel/infrastructure/channels/slack/block_kit.py` (new)
- `tests/unit/channels/slack/test_adapter.py` (new)
- `tests/unit/channels/slack/test_block_kit.py` (new)

**After:**
```python
# src/lintel/infrastructure/channels/slack/adapter.py
"""SlackChannelAdapter -- implements ChannelAdapter protocol via slack-bolt."""

from __future__ import annotations

from typing import Any

import structlog
from slack_sdk.web.async_client import AsyncWebClient

logger = structlog.get_logger()


class SlackChannelAdapter:
    """Implements ChannelAdapter protocol with Slack Web API."""

    def __init__(self, client: AsyncWebClient) -> None:
        self._client = client

    async def send_message(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await self._client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
        return dict(result)

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await self._client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=text,
            blocks=blocks,
        )
        return dict(result)

    async def send_approval_request(
        self,
        channel_id: str,
        thread_ts: str,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]:
        from lintel.infrastructure.channels.slack.block_kit import (
            build_approval_blocks,
        )

        blocks = build_approval_blocks(gate_type, summary, callback_id)
        return await self.send_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=f"Approval required: {gate_type}",
            blocks=blocks,
        )
```

```python
# src/lintel/infrastructure/channels/slack/block_kit.py
"""Block Kit builders. Domain RichContent -> Slack Block Kit JSON."""

from __future__ import annotations

from typing import Any


def build_approval_blocks(
    gate_type: str,
    summary: str,
    callback_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Approval Required: {gate_type}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": f"approve:{gate_type}:{callback_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": f"reject:{gate_type}:{callback_id}",
                },
            ],
        },
    ]


def build_status_blocks(
    agent_name: str,
    phase: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{agent_name}* | Phase: `{phase}`",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:3000]},
        },
    ]
    if metadata:
        context_elements = [
            {"type": "mrkdwn", "text": f"*{k}*: {v}"}
            for k, v in metadata.items()
        ]
        blocks.append({
            "type": "context",
            "elements": context_elements[:10],
        })
    return blocks
```

**Test Strategy:**
- Unit: Event translator with sample Slack payloads
- Unit: Block Kit builder output structure
- Unit: Approval action translation

**Validation:**
```bash
task test -- tests/unit/channels/slack/
```

---

### Phase 7: Workflow Engine (LangGraph)

**Objective:** Implement the workflow engine using LangGraph behind Lintel's own abstractions. Build the feature-to-PR workflow graph with approval gates and parallel agent spawning.
**Dependencies:** Phases 3, 6

#### Step 7.1: Workflow State and Graph Definition

**Files:**
- `src/lintel/workflows/state.py` (new)
- `src/lintel/workflows/feature_to_pr.py` (new)
- `src/lintel/workflows/nodes/ingest.py` (new)
- `src/lintel/workflows/nodes/route.py` (new)
- `src/lintel/workflows/nodes/plan.py` (new)
- `src/lintel/workflows/nodes/implement.py` (new)
- `src/lintel/workflows/nodes/review.py` (new)
- `tests/unit/workflows/__init__.py` (new)
- `tests/unit/workflows/test_feature_to_pr.py` (new)

**After:**
```python
# src/lintel/workflows/state.py
"""Workflow state definitions. TypedDict for LangGraph compatibility."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
from operator import add


class ThreadWorkflowState(TypedDict):
    """State for the feature-to-PR workflow graph."""
    thread_ref: str
    correlation_id: str
    current_phase: str
    sanitized_messages: Annotated[list[str], add]
    intent: str
    plan: dict[str, Any]
    agent_outputs: Annotated[list[dict[str, Any]], add]
    pending_approvals: list[str]
    sandbox_results: Annotated[list[dict[str, Any]], add]
    pr_url: str
    error: str | None
```

```python
# src/lintel/workflows/feature_to_pr.py
"""Feature-to-PR workflow graph using LangGraph.

LangGraph is an implementation detail. This module wraps it behind
Lintel's own graph builder so the orchestration engine can be replaced.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from lintel.workflows.state import ThreadWorkflowState
from lintel.workflows.nodes.ingest import ingest_message
from lintel.workflows.nodes.route import route_intent
from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.implement import spawn_implementation
from lintel.workflows.nodes.review import review_output


def build_feature_to_pr_graph() -> StateGraph:
    """Build the feature-to-PR workflow graph."""
    graph = StateGraph(ThreadWorkflowState)

    graph.add_node("ingest", ingest_message)
    graph.add_node("route", route_intent)
    graph.add_node("plan", plan_work)
    graph.add_node("approval_gate_spec", lambda s: s)
    graph.add_node("implement", spawn_implementation)
    graph.add_node("review", review_output)
    graph.add_node("approval_gate_merge", lambda s: s)
    graph.add_node("close", lambda s: {**s, "current_phase": "closed"})

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "route")
    graph.add_conditional_edges("route", _route_decision, {
        "plan": "plan",
        "close": "close",
    })
    graph.add_edge("plan", "approval_gate_spec")
    graph.add_edge("approval_gate_spec", "implement")
    graph.add_edge("implement", "review")
    graph.add_edge("review", "approval_gate_merge")
    graph.add_edge("approval_gate_merge", "close")
    graph.add_edge("close", END)

    return graph


def _route_decision(state: ThreadWorkflowState) -> str:
    intent = state.get("intent", "")
    if intent in ("feature", "bug", "refactor"):
        return "plan"
    return "close"


async def compile_workflow(db_url: str):
    """Compile the workflow with Postgres checkpointing."""
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    await checkpointer.setup()

    graph = build_feature_to_pr_graph()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval_gate_spec", "approval_gate_merge"],
    )
```

```python
# src/lintel/workflows/nodes/ingest.py
"""Ingest node: processes incoming message through PII firewall."""

from __future__ import annotations

from typing import Any

from lintel.workflows.state import ThreadWorkflowState


async def ingest_message(state: ThreadWorkflowState) -> dict[str, Any]:
    """Process message. PII firewall runs before this node."""
    return {
        "current_phase": "ingesting",
        "sanitized_messages": state.get("sanitized_messages", []),
    }
```

```python
# src/lintel/workflows/nodes/route.py
"""Route node: classifies intent from message content."""

from __future__ import annotations

from typing import Any

from lintel.workflows.state import ThreadWorkflowState


async def route_intent(state: ThreadWorkflowState) -> dict[str, Any]:
    """Classify user intent. v0.1: keyword matching. Later: LLM."""
    messages = state.get("sanitized_messages", [])
    combined = " ".join(messages).lower()

    intent = "feature"
    if any(word in combined for word in ["bug", "fix", "broken", "error"]):
        intent = "bug"
    elif any(word in combined for word in ["refactor", "clean", "modernize"]):
        intent = "refactor"

    return {"intent": intent, "current_phase": "planning"}
```

```python
# src/lintel/workflows/nodes/plan.py
"""Plan node: generates implementation plan via agent runtime."""

from __future__ import annotations

from typing import Any

from lintel.workflows.state import ThreadWorkflowState


async def plan_work(state: ThreadWorkflowState) -> dict[str, Any]:
    """Generate work plan. v0.1: placeholder. Later: LLM agent."""
    return {
        "plan": {
            "tasks": ["Implement feature", "Write tests", "Create PR"],
            "intent": state.get("intent", "feature"),
        },
        "current_phase": "awaiting_spec_approval",
        "pending_approvals": ["spec_approval"],
    }
```

```python
# src/lintel/workflows/nodes/implement.py
"""Implement node: spawns sandbox jobs for coding agents."""

from __future__ import annotations

from typing import Any

from lintel.workflows.state import ThreadWorkflowState


async def spawn_implementation(state: ThreadWorkflowState) -> dict[str, Any]:
    """Spawn implementation. v0.1: placeholder. Later: parallel sandboxes."""
    return {
        "current_phase": "implementing",
        "pending_approvals": [],
        "sandbox_results": [{"status": "completed", "artifacts": {}}],
    }
```

```python
# src/lintel/workflows/nodes/review.py
"""Review node: runs code review agent on implementation output."""

from __future__ import annotations

from typing import Any

from lintel.workflows.state import ThreadWorkflowState


async def review_output(state: ThreadWorkflowState) -> dict[str, Any]:
    """Review implementation output. v0.1: placeholder. Later: LLM agent."""
    return {
        "current_phase": "awaiting_merge_approval",
        "pending_approvals": ["merge_approval"],
        "agent_outputs": [{"role": "reviewer", "output": "LGTM"}],
    }
```

**Test Strategy:**
- Unit: Graph structure (node count, edge connections)
- Unit: Route decision logic
- Integration: Full graph execution with mock nodes and Postgres checkpointing

**Validation:**
```bash
task test -- tests/unit/workflows/
task typecheck
```

---

### Phase 8: Agent Runtime & Model Router

**Objective:** Implement the agent runtime that executes agent steps with configurable model policies, and the model router using litellm for multi-provider support.
**Dependencies:** Phase 7

#### Step 8.1: Model Router

**Files:**
- `src/lintel/infrastructure/models/router.py` (new)
- `src/lintel/infrastructure/models/litellm_provider.py` (new)
- `tests/unit/infrastructure/test_model_router.py` (new)

**After:**
```python
# src/lintel/infrastructure/models/router.py
"""Model router: selects provider + model per agent role and workload type."""

from __future__ import annotations

from typing import Any

import structlog

from lintel.contracts.types import AgentRole, ModelPolicy

logger = structlog.get_logger()

DEFAULT_ROUTING: dict[tuple[str, str], ModelPolicy] = {
    ("planner", "planning"): ModelPolicy(
        "anthropic", "claude-sonnet-4-20250514", 8192, 0.1,
    ),
    ("coder", "coding"): ModelPolicy(
        "anthropic", "claude-sonnet-4-20250514", 16384, 0.0,
    ),
    ("reviewer", "review"): ModelPolicy(
        "anthropic", "claude-sonnet-4-20250514", 8192, 0.0,
    ),
    ("summarizer", "summarize"): ModelPolicy(
        "anthropic", "claude-haiku-35-20241022", 4096, 0.0,
    ),
}

FALLBACK_POLICY = ModelPolicy("ollama", "llama3.1:8b", 4096, 0.0)


class DefaultModelRouter:
    """Implements ModelRouter protocol with a routing table."""

    def __init__(
        self,
        routing_table: dict[tuple[str, str], ModelPolicy] | None = None,
        fallback: ModelPolicy = FALLBACK_POLICY,
    ) -> None:
        self._routing = routing_table or DEFAULT_ROUTING
        self._fallback = fallback

    async def select_model(
        self,
        agent_role: AgentRole,
        workload_type: str,
    ) -> ModelPolicy:
        key = (agent_role.value, workload_type)
        policy = self._routing.get(key, self._fallback)
        logger.info(
            "model_selected",
            agent_role=agent_role.value,
            workload_type=workload_type,
            provider=policy.provider,
            model=policy.model_name,
        )
        return policy

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        import litellm

        model_string = f"{policy.provider}/{policy.model_name}"
        kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "max_tokens": policy.max_tokens,
            "temperature": policy.temperature,
        }
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(**kwargs)
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            "model": response.model,
        }
```

#### Step 8.2: Agent Runtime

**Files:**
- `src/lintel/agents/runtime.py` (new)
- `src/lintel/agents/session.py` (new)
- `tests/unit/agents/__init__.py` (new)
- `tests/unit/agents/test_runtime.py` (new)

**After:**
```python
# src/lintel/agents/runtime.py
"""Agent runtime: executes agent steps with model + tools + event emission."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog

from lintel.contracts.events import (
    AgentStepCompleted,
    AgentStepStarted,
    ModelCallCompleted,
    ModelSelected,
)
from lintel.contracts.protocols import EventStore, ModelRouter
from lintel.contracts.types import ActorType, AgentRole, ThreadRef

logger = structlog.get_logger()


class AgentRuntime:
    """Executes agent steps, routing to models and emitting events."""

    def __init__(
        self,
        event_store: EventStore,
        model_router: ModelRouter,
    ) -> None:
        self._event_store = event_store
        self._model_router = model_router

    async def execute_step(
        self,
        thread_ref: ThreadRef,
        agent_role: AgentRole,
        step_name: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        correlation_id: Any = None,
    ) -> dict[str, Any]:
        cid = correlation_id or uuid4()

        # Emit step started
        await self._event_store.append(
            thread_ref.stream_id,
            [AgentStepStarted(
                actor_type=ActorType.AGENT,
                actor_id=agent_role.value,
                thread_ref=thread_ref,
                correlation_id=cid,
                payload={
                    "agent_role": agent_role.value,
                    "step_name": step_name,
                },
            )],
        )

        # Select model
        policy = await self._model_router.select_model(
            agent_role, step_name,
        )
        await self._event_store.append(
            thread_ref.stream_id,
            [ModelSelected(
                actor_type=ActorType.SYSTEM,
                actor_id="model_router",
                thread_ref=thread_ref,
                correlation_id=cid,
                payload={
                    "agent_role": agent_role.value,
                    "provider": policy.provider,
                    "model_name": policy.model_name,
                },
            )],
        )

        # Call model
        result = await self._model_router.call_model(
            policy, messages, tools,
        )

        # Emit model call completed
        await self._event_store.append(
            thread_ref.stream_id,
            [ModelCallCompleted(
                actor_type=ActorType.SYSTEM,
                actor_id="model_router",
                thread_ref=thread_ref,
                correlation_id=cid,
                payload={
                    "provider": policy.provider,
                    "model": result.get("model", policy.model_name),
                    "input_tokens": result.get("usage", {}).get(
                        "input_tokens", 0,
                    ),
                    "output_tokens": result.get("usage", {}).get(
                        "output_tokens", 0,
                    ),
                },
            )],
        )

        # Emit step completed
        await self._event_store.append(
            thread_ref.stream_id,
            [AgentStepCompleted(
                actor_type=ActorType.AGENT,
                actor_id=agent_role.value,
                thread_ref=thread_ref,
                correlation_id=cid,
                payload={
                    "agent_role": agent_role.value,
                    "step_name": step_name,
                    "output_summary": result.get("content", "")[:500],
                },
            )],
        )

        return result
```

**Test Strategy:**
- Unit: Model router selection logic with mock routing table
- Unit: Agent runtime event emission sequence with mock event store
- Integration: Full agent step with mock LLM

**Validation:**
```bash
task test -- tests/unit/agents/
task test -- tests/unit/infrastructure/test_model_router.py
```

---

### Phase 9: Skill Registry

**Objective:** Dynamic skill registration, versioning, discovery, and invocation with permission checks.
**Dependencies:** Phase 2 (contracts), Phase 8 (agent runtime)

#### Step 9.1: Skill Protocol & Registry

**Files:**
- `src/lintel/domain/skills/protocols.py` (new)
- `src/lintel/domain/skills/registry.py` (new)
- `src/lintel/domain/skills/models.py` (new)

**After:**
```python
# src/lintel/domain/skills/protocols.py
from typing import Any, Protocol
from lintel.contracts.types import SkillDescriptor, SkillResult

class Skill(Protocol):
    @property
    def descriptor(self) -> SkillDescriptor: ...

    async def execute(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult: ...


class SkillRegistry(Protocol):
    async def register(self, skill: Skill) -> None: ...
    async def deregister(self, skill_name: str, version: str) -> None: ...
    async def get(self, skill_name: str, version: str | None = None) -> Skill: ...
    async def list_skills(self) -> list[SkillDescriptor]: ...
    async def list_for_agent(self, agent_role: str) -> list[SkillDescriptor]: ...
```

```python
# src/lintel/domain/skills/registry.py
from lintel.domain.skills.protocols import Skill, SkillRegistry
from lintel.contracts.types import SkillDescriptor, SkillResult

class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Skill]] = {}  # name -> version -> skill

    async def register(self, skill: Skill) -> None:
        desc = skill.descriptor
        self._skills.setdefault(desc.name, {})[desc.version] = skill

    async def deregister(self, skill_name: str, version: str) -> None:
        if skill_name in self._skills:
            self._skills[skill_name].pop(version, None)

    async def get(self, skill_name: str, version: str | None = None) -> Skill:
        versions = self._skills.get(skill_name)
        if not versions:
            raise KeyError(f"Skill not found: {skill_name}")
        if version:
            return versions[version]
        # Return latest version
        latest = sorted(versions.keys())[-1]
        return versions[latest]

    async def list_skills(self) -> list[SkillDescriptor]:
        return [
            skill.descriptor
            for versions in self._skills.values()
            for skill in versions.values()
        ]

    async def list_for_agent(self, agent_role: str) -> list[SkillDescriptor]:
        return [
            d for d in await self.list_skills()
            if agent_role in d.allowed_agent_roles
        ]
```

#### Step 9.2: Built-in Skills (Code, Test, Review)

**Files:**
- `src/lintel/infrastructure/skills/code_skill.py` (new)
- `src/lintel/infrastructure/skills/test_skill.py` (new)
- `src/lintel/infrastructure/skills/review_skill.py` (new)

#### Step 9.3: Skill Invocation Events

**Files:**
- Update `src/lintel/contracts/events.py` — add `SkillInvoked`, `SkillSucceeded`, `SkillFailed`

**Test Strategy:**
- Unit: Registry CRUD operations
- Unit: Skill permission filtering by agent role
- Unit: Skill invocation event emission

**Validation:**
```bash
task test -- tests/unit/skills/
```

---

### Phase 10: Sandbox Manager

**Objective:** Docker-based sandbox lifecycle with defense-in-depth security, devcontainer support, and artifact collection.
**Dependencies:** Phase 2 (contracts), Phase 8 (agent runtime)

#### Step 10.1: Sandbox Protocol & Docker Backend

**Files:**
- `src/lintel/domain/sandbox/protocols.py` (new)
- `src/lintel/infrastructure/sandbox/docker_backend.py` (new)
- `src/lintel/infrastructure/sandbox/models.py` (new)

**After:**
```python
# src/lintel/domain/sandbox/protocols.py
from typing import Protocol
from lintel.contracts.types import (
    SandboxConfig, SandboxJob, SandboxResult, ThreadRef,
)

class SandboxManager(Protocol):
    async def create(
        self,
        config: SandboxConfig,
        thread_ref: ThreadRef,
    ) -> str:
        """Create sandbox, return sandbox_id."""
        ...

    async def execute(
        self,
        sandbox_id: str,
        job: SandboxJob,
    ) -> SandboxResult: ...

    async def collect_artifacts(self, sandbox_id: str) -> list[dict]: ...
    async def destroy(self, sandbox_id: str) -> None: ...
```

```python
# src/lintel/infrastructure/sandbox/docker_backend.py
import asyncio
from uuid import uuid4
import docker
from lintel.domain.sandbox.protocols import SandboxManager
from lintel.contracts.types import SandboxConfig, SandboxJob, SandboxResult, ThreadRef

class DockerSandboxManager:
    def __init__(self) -> None:
        self._client = docker.from_env()
        self._containers: dict[str, docker.models.containers.Container] = {}

    async def create(
        self, config: SandboxConfig, thread_ref: ThreadRef,
    ) -> str:
        sandbox_id = str(uuid4())

        container = await asyncio.to_thread(
            self._client.containers.create,
            image=config.image,
            command="sleep infinity",
            detach=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            read_only=True,
            network_mode="none",
            mem_limit=config.memory_limit or "512m",
            cpu_period=100000,
            cpu_quota=config.cpu_quota or 50000,
            user="1000:1000",
            tmpfs={"/tmp": "size=100m,noexec"},
            labels={
                "lintel.sandbox_id": sandbox_id,
                "lintel.thread_ref": thread_ref.stream_id,
            },
        )
        await asyncio.to_thread(container.start)
        self._containers[sandbox_id] = container
        return sandbox_id

    async def execute(
        self, sandbox_id: str, job: SandboxJob,
    ) -> SandboxResult:
        container = self._containers[sandbox_id]
        exec_result = await asyncio.to_thread(
            container.exec_run,
            cmd=job.command,
            workdir=job.workdir or "/workspace",
        )
        return SandboxResult(
            exit_code=exec_result.exit_code,
            stdout=exec_result.output.decode("utf-8", errors="replace"),
        )

    async def collect_artifacts(self, sandbox_id: str) -> list[dict]:
        # Collect diffs, logs, test results from sandbox
        container = self._containers[sandbox_id]
        result = await asyncio.to_thread(
            container.exec_run, cmd="git diff", workdir="/workspace",
        )
        return [{"type": "diff", "content": result.output.decode()}]

    async def destroy(self, sandbox_id: str) -> None:
        container = self._containers.pop(sandbox_id, None)
        if container:
            await asyncio.to_thread(container.remove, force=True)
```

#### Step 10.2: Sandbox Events

**Files:**
- Update `src/lintel/contracts/events.py` — add `SandboxCreated`, `SandboxCommandExecuted`, `SandboxArtifactsCollected`, `SandboxDestroyed`

**Test Strategy:**
- Unit: Sandbox config validation
- Unit: Docker create flags include defense-in-depth (cap_drop, read_only, network_mode)
- Integration: Full sandbox lifecycle with Docker (requires Docker daemon)

**Validation:**
```bash
task test -- tests/unit/sandbox/
task test -- tests/integration/test_sandbox.py  # requires Docker
```

---

### Phase 11: Repo Provider (GitHub)

**Objective:** Git and PR operations behind a protocol, with GitHub as first implementation.
**Dependencies:** Phase 10 (sandbox manager)

#### Step 11.1: Repo Protocol & GitHub Implementation

**Files:**
- `src/lintel/domain/repo/protocols.py` (new)
- `src/lintel/infrastructure/repo/github_provider.py` (new)

**After:**
```python
# src/lintel/domain/repo/protocols.py
from typing import Protocol

class RepoProvider(Protocol):
    async def clone(self, repo_url: str, branch: str, dest: str) -> None: ...
    async def create_branch(self, repo_url: str, base: str, name: str) -> None: ...
    async def commit_and_push(self, workdir: str, message: str, branch: str) -> str: ...
    async def create_pr(
        self, repo_url: str, head: str, base: str, title: str, body: str,
    ) -> str: ...
    async def add_comment(self, repo_url: str, pr_number: int, body: str) -> None: ...
```

#### Step 11.2: Repo Events

**Files:**
- Update `src/lintel/contracts/events.py` — add `BranchCreated`, `CommitCreated`, `PRCreated`

**Test Strategy:**
- Unit: GitHub provider with mocked httpx
- Unit: Repo event emission

**Validation:**
```bash
task test -- tests/unit/repo/
```

---

### Phase 12: Projections & Read Models

**Objective:** Event-driven projections that maintain queryable views from the event stream.
**Dependencies:** Phase 3 (event store)

#### Step 12.1: Projection Engine

**Files:**
- `src/lintel/domain/projections/protocols.py` (new)
- `src/lintel/infrastructure/projections/engine.py` (new)
- `src/lintel/infrastructure/projections/thread_status.py` (new)
- `src/lintel/infrastructure/projections/task_backlog.py` (new)

**After:**
```python
# src/lintel/domain/projections/protocols.py
from typing import Protocol
from lintel.contracts.events import DomainEvent

class Projection(Protocol):
    """A projection that builds a read model from events."""
    @property
    def handled_event_types(self) -> set[str]: ...

    async def project(self, event: DomainEvent) -> None: ...
    async def rebuild(self, events: list[DomainEvent]) -> None: ...


class ProjectionEngine(Protocol):
    async def register(self, projection: Projection) -> None: ...
    async def project(self, event: DomainEvent) -> None: ...
    async def rebuild_all(self, stream_id: str) -> None: ...
```

```python
# src/lintel/infrastructure/projections/thread_status.py
from lintel.contracts.events import DomainEvent
from lintel.domain.projections.protocols import Projection

class ThreadStatusProjection:
    """Maintains thread_status_view table."""

    @property
    def handled_event_types(self) -> set[str]:
        return {
            "ThreadMessageReceived",
            "WorkflowStarted",
            "WorkflowAdvanced",
            "HumanApprovalGranted",
            "HumanApprovalRejected",
            "PRMerged",
        }

    async def project(self, event: DomainEvent) -> None:
        # Upsert into thread_status_view
        # Fields: thread_ref, status, last_event_type, last_event_at, event_count
        ...

    async def rebuild(self, events: list[DomainEvent]) -> None:
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)
```

#### Step 12.2: Projection SQL Migrations

**Files:**
- `migrations/003_projections.sql` (new) — `thread_status_view`, `task_backlog_view`, `audit_view`

**Test Strategy:**
- Unit: Projection handles correct event types
- Integration: Thread status projection with real Postgres
- Integration: Rebuild from event stream produces correct state

**Validation:**
```bash
task test -- tests/unit/projections/
task test -- tests/integration/test_projections.py
```

---

### Phase 13: API Layer & FastAPI App

**Objective:** FastAPI application wiring all modules together with dependency injection, health endpoint, and thread/event query endpoints.
**Dependencies:** Phases 6-12

#### Step 13.1: FastAPI App & Lifespan

**Files:**
- `src/lintel/api/app.py` (new)
- `src/lintel/api/deps.py` (new)
- `src/lintel/api/routes/health.py` (new)
- `src/lintel/api/routes/threads.py` (new)
- `src/lintel/api/middleware.py` (new)

**After:**
```python
# src/lintel/api/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from lintel.api.routes import health, threads
from lintel.api.middleware import CorrelationMiddleware
from lintel.infrastructure.config import Settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    # Initialize event store, PII firewall, etc.
    # Store in app.state for dependency injection
    yield
    # Cleanup

def create_app() -> FastAPI:
    app = FastAPI(title="Lintel", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health.router)
    app.include_router(threads.router, prefix="/api/v1")
    return app

app = create_app()
```

```python
# src/lintel/api/middleware.py
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

**Test Strategy:**
- Integration: Health endpoint returns 200
- Integration: Thread events endpoint with seeded data
- Integration: Correlation ID propagation through middleware

**Validation:**
```bash
task test -- tests/integration/test_api.py
task serve  # manual smoke test at localhost:8000/healthz
```

---

### Phase 14: Docker Compose & Local Dev

**Objective:** Docker Compose setup for local development with all infrastructure dependencies.
**Dependencies:** Phase 13

#### Step 14.1: Docker Compose

**Files:**
- `ops/docker-compose.yaml` (new)
- `Dockerfile` (new)
- `.env.example` (new)

**After:**
```yaml
# ops/docker-compose.yaml
services:
  postgres:
    image: postgres:16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: lintel
      POSTGRES_USER: lintel
      POSTGRES_PASSWORD: lintel
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lintel"]
      interval: 5s
      timeout: 5s
      retries: 5

  nats:
    image: nats:2.10
    ports:
      - "4222:4222"
      - "8222:8222"
    command: ["--jetstream", "--http_port", "8222"]
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:8222/healthz"]
      interval: 5s
      timeout: 3s
      retries: 5

  lintel:
    build:
      context: ..
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      LINTEL_DB_DSN: postgresql://lintel:lintel@postgres:5432/lintel
      LINTEL_NATS_URL: nats://nats:4222
      LINTEL_SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN:-}
      LINTEL_SLACK_SIGNING_SECRET: ${SLACK_SIGNING_SECRET:-}
      LINTEL_SLACK_APP_TOKEN: ${SLACK_APP_TOKEN:-}
      LINTEL_PII_VAULT_ENCRYPTION_KEY: ${PII_VAULT_ENCRYPTION_KEY:-}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  pgdata:
```

```dockerfile
# Dockerfile
FROM python:3.12-slim AS base

RUN groupadd -r lintel && useradd -r -g lintel lintel
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY migrations/ migrations/

USER lintel
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "lintel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Test Strategy:**
- Manual: `docker compose up` starts all services
- Manual: Health endpoint accessible at localhost:8000/healthz

**Validation:**
```bash
cd ops && docker compose up -d
curl http://localhost:8000/healthz
cd ops && docker compose down
```

---

### Phase 15: Integration Tests & E2E

**Objective:** Full integration test suite covering critical paths.
**Dependencies:** Phase 14

#### Step 15.1: Integration Test Suite

**Files:**
- `tests/integration/test_full_pipeline.py` (new)
- `tests/integration/test_pii_pipeline.py` (new)
- `tests/integration/test_workflow_lifecycle.py` (new)

**After:**
```python
# tests/integration/test_full_pipeline.py
"""Integration test: message ingestion through event store and projection."""

import pytest
from uuid import uuid4

from lintel.contracts.events import ThreadMessageReceived, WorkflowStarted
from lintel.contracts.types import ActorType, ThreadRef


async def test_message_ingestion_pipeline(
    event_store, pii_firewall, projection_engine,
):
    """Full pipeline: raw message -> PII -> event store -> projection."""
    thread_ref = ThreadRef("W1", "C1", "test.ts")

    result = await pii_firewall.analyze_and_anonymize(
        "Please contact john@example.com for details",
        thread_ref,
    )
    assert not result.is_blocked
    assert "<EMAIL_1>" in result.sanitized_text

    events = [
        ThreadMessageReceived(
            actor_type=ActorType.HUMAN,
            actor_id="U123",
            thread_ref=thread_ref,
            correlation_id=uuid4(),
            payload={"sanitized_text": result.sanitized_text, "sender_id": "U123"},
        ),
    ]

    await event_store.append(thread_ref.stream_id, events)
    stored = await event_store.read_stream(thread_ref.stream_id)
    assert len(stored) == 1
    assert stored[0].event_type == "ThreadMessageReceived"
```

**Test Strategy:**
- Integration: Full message pipeline with real Postgres
- Integration: PII detection + vault round-trip
- Integration: Workflow lifecycle with checkpointing

**Validation:**
```bash
task test-integration
```

---

### Phase 16: Documentation & CI/CD

**Objective:** README, contributing guide, architecture docs, and GitHub Actions CI.
**Dependencies:** Phase 15

#### Step 16.1: Documentation

**Files:**
- `README.md` (modify)
- `CONTRIBUTING.md` (new)
- `docs/architecture.md` (new)
- `docs/events.md` (new)
- `docs/local-dev.md` (new)

#### Step 16.2: GitHub Actions CI

**Files:**
- `.github/workflows/ci.yaml` (new)

**After:**
```yaml
# .github/workflows/ci.yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/
      - run: uv run mypy src/lintel/

  test-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run pytest tests/unit -v --cov=src/lintel

  test-integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: lintel
          POSTGRES_USER: lintel
          POSTGRES_PASSWORD: lintel
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run pytest tests/integration -v
        env:
          LINTEL_DB_DSN: postgresql://lintel:lintel@localhost:5432/lintel
```

**Test Strategy:**
- CI: Lint + typecheck on every PR
- CI: Unit tests on every PR
- CI: Integration tests with Postgres service container

**Validation:**
```bash
task all  # runs lint, typecheck, test locally
```

---

## 4. Cross-Area Dependencies

```mermaid
graph LR
    P1[Phase 1: Skeleton] --> P2[Phase 2: Contracts]
    P2 --> P3[Phase 3: Event Store]
    P2 --> P4[Phase 4: PII Firewall]
    P2 --> P5[Phase 5: Config & Observability]
    P3 --> P6[Phase 6: Slack Adapter]
    P4 --> P6
    P3 --> P7[Phase 7: Workflow Engine]
    P6 --> P7
    P7 --> P8[Phase 8: Agent Runtime]
    P8 --> P9[Phase 9: Skill Registry]
    P8 --> P10[Phase 10: Sandbox Manager]
    P10 --> P11[Phase 11: Repo Provider]
    P3 --> P12[Phase 12: Projections]
    P6 --> P13[Phase 13: API Layer]
    P7 --> P13
    P8 --> P13
    P9 --> P13
    P10 --> P13
    P11 --> P13
    P12 --> P13
    P13 --> P14[Phase 14: Docker Compose]
    P14 --> P15[Phase 15: Integration Tests]
    P15 --> P16[Phase 16: Docs & CI]

    style P4 fill:#ffcccc
    style P5 fill:#ffcccc
    style P9 fill:#ccffcc
    style P10 fill:#ccffcc
```

**Parallel Execution Opportunities:**
- Phase 4 (PII) and Phase 5 (Config/Observability) can run in parallel after Phase 2
- Phase 9 (Skill Registry) and Phase 10 (Sandbox Manager) can run in parallel after Phase 8
- Phase 12 (Projections) can start as early as Phase 3 completes

**Blocking Dependencies:**
- Phase 2 (Contracts) blocks ALL subsequent phases — it defines the shared kernel
- Phase 3 (Event Store) blocks Phases 6, 7, and 12
- Phase 7 (Workflow Engine) blocks Phase 8 (Agent Runtime)
- Phase 13 (API Layer) requires all component phases (6-12) to be complete

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation | Fallback |
|------|--------|------------|----------|
| Event store schema lock-in | High | Invest in schema design in Phase 2-3 before application code. Include `schema_version` on every event. Build upcaster chain from day one. | Parallel event store with new schema + replay |
| LangGraph vendor coupling | High | Wrap LangGraph behind `workflows/` module. Domain never imports LangGraph directly. Graph builder abstraction in Phase 7. | Replace with Temporal or custom state machine |
| PII leakage past Presidio | High | Fail-closed behavior (block above threshold). Custom recognizers for code patterns (API keys, connection strings). Encrypted vault. | Add secondary NLP-based scanner; manual PII review queue |
| Sandbox container escape | Critical | Defense-in-depth: `cap-drop ALL`, seccomp, read-only rootfs, `network_mode=none`, non-root user. No Docker socket in sandboxes. | Add gVisor (runsc) runtime; Firecracker for managed tier |
| Async complexity causing bugs | Medium | Ban sync blocking via ruff rules. Structured logging with correlation IDs. `asyncio.to_thread()` for sync libs (Presidio, Docker SDK). Comprehensive async test fixtures. | Add synchronous execution mode for debugging |

---

## 6. Success Criteria

**Implementation Complete When:**
- [ ] All 16 phases complete
- [ ] `task lint` passes with zero warnings
- [ ] `task typecheck` passes with zero errors
- [ ] `task test-unit` passes (all unit tests green)
- [ ] `task test-integration` passes with testcontainers (Postgres, Docker)
- [ ] `docker compose up` starts all services successfully
- [ ] Health endpoint returns `{"status": "ok"}` at `GET /healthz`
- [ ] A Slack message triggers the PII firewall and creates events in the event store
- [ ] Workflow engine advances through ingest -> route -> plan phases
- [ ] Approval gate pauses workflow and resumes on Slack button click
- [ ] Agent runtime calls LLM via model router and emits ModelCallCompleted events
- [ ] Sandbox creates Docker container with defense-in-depth security
- [ ] Projections update thread_status_view from events
- [ ] All Protocol interfaces have at least one concrete implementation
- [ ] Event types include `schema_version` for future upcasting
- [ ] No Slack types leak outside `infrastructure/channels/slack/`
- [ ] No LangGraph imports outside `workflows/`
- [ ] No infrastructure imports inside `domain/` or `contracts/`