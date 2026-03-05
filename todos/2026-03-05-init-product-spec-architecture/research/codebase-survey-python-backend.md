# Codebase Survey - Python Backend

## Survey Context

Lintel is a greenfield project with no existing code. This survey documents reference implementations, architectural patterns, and design decisions for the Python backend.

---

## 1. Reference Architecture Patterns

### REPO-PY-01: Postgres Event Store Schema

The canonical pattern for a Postgres-based event store uses a single append-only table with optimistic concurrency control:

```sql
CREATE TABLE events (
    event_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id      TEXT NOT NULL,
    stream_version BIGINT NOT NULL,
    event_type     TEXT NOT NULL,
    payload        JSONB NOT NULL,
    metadata       JSONB NOT NULL,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (stream_id, stream_version)
);
CREATE INDEX idx_events_stream ON events (stream_id, stream_version);
```

The `UNIQUE (stream_id, stream_version)` constraint provides optimistic concurrency.

### REPO-PY-02: Python Event Sourcing Libraries

- **eventsourcing** (pypi): Mature Python ES library. Supports Postgres via `eventsourcing-postgres`. Provides aggregates, snapshots, and projection infrastructure.
- **esdbclient**: Python client for EventStoreDB.
- **Custom implementation**: Given Lintel's specific envelope (hash chaining, thread_ref correlation), a thin custom layer over asyncpg is the best fit.

### REPO-PY-03: Projection Pattern

Use a separate async consumer that reads events from the store and maintains materialized views. For v0.1, a synchronous in-process projection that runs after event append is simplest. For scale, use PostgreSQL LISTEN/NOTIFY or a NATS consumer.

### REPO-PY-04: LangGraph StateGraph Pattern

LangGraph models workflows as directed graphs with typed state:

- **StateGraph with TypedDict state**: Define thread workflow state including `thread_ref`, `current_phase`, `agent_outputs`, `pending_approvals`.
- **Conditional edges**: Route between nodes based on intent classification or approval status.
- **Human-in-the-loop via interrupt**: `interrupt_before` and `interrupt_after` on nodes maps directly to approval gates.
- **Checkpointing**: `PostgresSaver` persists graph state. Each state transition emits a `WorkflowAdvanced` event.
- **Subgraphs**: For parallel agent spawning.

### REPO-PY-05: LangGraph Parallelism

Use `Send` API to dispatch multiple parallel branches:

```python
from langgraph.graph import StateGraph, Send

def spawn_agents(state):
    return [Send("agent_step", {"role": role, "context": state["context"]})
            for role in state["required_roles"]]

graph.add_conditional_edges("plan", spawn_agents)
```

### REPO-PY-06: LangGraph Persistence

Use `langgraph-checkpoint-postgres` for durable workflow state. Enables crash recovery and long-running workflows.

### REPO-PY-07: FastAPI Patterns for Event-Sourced Systems

- **Command endpoints** (POST): Accept commands, validate with Pydantic, dispatch to domain logic.
- **Query endpoints** (GET): Read from projections, not event streams.
- **Webhook endpoints**: For Slack events API.
- **WebSocket endpoints**: For real-time thread status updates.
- **Dependency injection**: FastAPI's `Depends()` system.

### REPO-PY-08: Presidio Integration

- `presidio-analyzer` detects PII entities.
- `presidio-anonymizer` replaces detected entities with operators.
- For stable placeholders within a thread, use a custom operator mapping each entity to a deterministic placeholder (e.g., `<PERSON_1>`, `<EMAIL_2>`).
- Pipeline: `raw_text -> AnalyzerEngine.analyze() -> AnonymizerEngine.anonymize() -> sanitized_text` plus emit events.

### REPO-PY-09: Model Routing Pattern

- Define a `ModelPolicy` dataclass per agent role.
- `ModelRouter` takes `(agent_role, workload_type, sensitivity_level)` and returns `(provider, model_name, parameters)`.
- Use strategy pattern with a policy engine (simple rule table in Postgres for v0.1).
- Emit `ModelSelected` event before every LLM call.

---

## 2. Recommended Project Structure

### REPO-PY-10: Python Monorepo Layout

```
lintel/
├── pyproject.toml
├── src/
│   └── lintel/
│       ├── contracts/          # Shared schemas and protocols
│       │   ├── events.py       # Event envelope + all event types
│       │   ├── commands.py     # Command schemas
│       │   ├── skills.py       # Skill I/O schemas
│       │   ├── protocols.py    # ABCs: ChannelAdapter, Deidentifier, etc.
│       │   └── types.py        # ThreadRef, AgentRole, ModelPolicy
│       ├── domain/             # Pure domain logic (no I/O)
│       │   ├── thread.py
│       │   ├── workflow.py
│       │   ├── pii.py
│       │   ├── policy.py
│       │   └── model_routing.py
│       ├── infrastructure/     # Adapters and I/O
│       │   ├── event_store/
│       │   ├── channels/slack.py
│       │   ├── pii/presidio.py
│       │   ├── models/         # anthropic.py, bedrock.py, ollama.py
│       │   ├── repos/github.py
│       │   ├── sandbox/        # manager.py, docker.py
│       │   └── vault/
│       ├── workflows/          # LangGraph definitions
│       │   ├── feature_to_pr.py
│       │   ├── review.py
│       │   └── nodes/
│       ├── agents/             # Agent runtime
│       ├── skills/             # Built-in skills + registry
│       ├── api/                # FastAPI application
│       │   ├── app.py
│       │   ├── deps.py
│       │   ├── routes/
│       │   └── middleware/
│       ├── projections/        # Read model builders
│       └── config.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── ops/
└── migrations/
```

### REPO-PY-11: Module Boundary Rationale

- `contracts/` is the shared kernel — all modules depend on it, it depends on nothing.
- `domain/` contains pure business logic with no I/O.
- `infrastructure/` implements protocols defined in `contracts/`.
- `workflows/` contains LangGraph graph definitions.
- `api/` is a thin HTTP layer that delegates to domain and workflows.

---

## 3. Key Design Decisions

### REPO-PY-12: Async Throughout
FastAPI, asyncpg, LangGraph, and LLM calls are all async-native. Presidio is sync-only; wrap in `asyncio.to_thread()`.

### REPO-PY-13: Dependency Injection
FastAPI's built-in `Depends()` + simple service container. Define protocols in `contracts/`, wire in `api/deps.py`.

### REPO-PY-14: Configuration Management
pydantic-settings with typed `Settings` classes, loaded from environment variables.

### REPO-PY-15: Error Handling
Domain exception hierarchy: `LintelError -> DomainError, InfrastructureError, PolicyViolationError`. FastAPI exception handlers translate to HTTP responses.

### REPO-PY-16: Logging and Observability
- Structured logging with `structlog` (JSON output)
- OpenTelemetry distributed tracing
- Prometheus-compatible metrics
- Correlation ID propagation via `contextvars.ContextVar`

---

## 4. Reference Projects

### REPO-PY-17: Event-Sourced Python Backends
- `johnbywater/eventsourcing`: Most mature Python ES library
- Marten (.NET): Best Postgres-as-event-store documentation
- Message DB: Purpose-built Postgres event store

### REPO-PY-18: LangGraph Production Applications
- `langchain-ai/langgraph`: Official repo with examples
- `langchain-ai/opengpts`: Multi-agent platform using LangGraph + FastAPI + Postgres

### REPO-PY-19: Multi-Agent Systems
- `microsoft/autogen`, `crewai/crewai`, `langchain-ai/opengpts`

### REPO-PY-20: Presidio References
- `microsoft/presidio`: Includes FastAPI service samples and custom recognizer examples

### REPO-PY-21: Recommended Core Dependencies

| Concern | Library |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Database driver | asyncpg |
| ORM/query builder | SQLAlchemy 2.0 (async) |
| Event sourcing | Custom thin layer over asyncpg |
| Workflow engine | langgraph + langgraph-checkpoint-postgres |
| LLM integration | litellm or direct SDKs |
| PII pipeline | presidio-analyzer + presidio-anonymizer |
| Configuration | pydantic-settings |
| Logging | structlog |
| Tracing | opentelemetry-sdk |
| HTTP client | httpx |
| Task retry | tenacity |
| Testing | pytest + pytest-asyncio + testcontainers |
| Package management | uv |

### REPO-PY-22: Critical Path Build Order

1. Contracts first (event envelope, event types, protocols)
2. Event store (Postgres append-only)
3. PII firewall (Presidio adapter)
4. Slack adapter
5. Workflow engine (first LangGraph graph)
6. Agent runtime + model router
7. Sandbox manager
8. API layer
9. Projections
