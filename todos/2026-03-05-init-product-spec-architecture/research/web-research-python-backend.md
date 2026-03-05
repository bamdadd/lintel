# Web Research - Python Backend

## Current Best Practices (2024-2025) for Python Event-Sourced AI Platforms

---

## 1. Event Sourcing in Python (WEB-PY-01 to WEB-PY-06)

### WEB-PY-01: Postgres as Event Store (Production)

Multiple production systems use Postgres as their primary event store:
- **Marten** (.NET ecosystem) has proven Postgres event store patterns at scale
- **Message DB** is a purpose-built Postgres event store with ~50K events/sec write throughput
- **Custom implementations** are common in Python due to lack of a dominant ES library

Key insight: Postgres with proper indexing and partitioning handles 10-50M events/day on a single writer node. Beyond that, consider EventStoreDB or a dedicated solution.

**Confidence**: 0.90

### WEB-PY-02: Event Schema Evolution

Industry consensus (2024-2025):
- Include `schema_version` on every event type from day one
- Implement upcasters that transform old event versions to current
- Never modify existing event schemas; create new versions
- Store events in their original schema; upcasting happens at read time
- JSON Schema or Pydantic models for validation

**Confidence**: 0.90

### WEB-PY-03: CQRS with Event Sourcing

Best practice pattern:
- Write side: validate command -> append events
- Read side: project events -> materialized views
- Separate models for writes (event streams) and reads (projections)
- Projections are disposable and rebuildable from events
- Use optimistic concurrency on event streams

**Confidence**: 0.95

### WEB-PY-04: asyncpg Performance

Benchmarks show asyncpg is 2-5x faster than psycopg2 for typical workloads:
- Connection pooling with `create_pool(min_size=5, max_size=20)`
- Prepared statements for hot paths (event append, stream read)
- Binary protocol gives significant speedup over text protocol
- Copy protocol for bulk event loading during projection rebuild

**Confidence**: 0.85

### WEB-PY-05: Idempotency Patterns

Production recommendations:
- Idempotency key in event metadata (UUID, derived from command)
- UNIQUE constraint on `(stream_id, stream_version)` for optimistic concurrency
- Deduplication table for at-least-once consumers
- Conditional writes: `INSERT ... ON CONFLICT DO NOTHING`

**Confidence**: 0.90

### WEB-PY-06: Event Store Performance Tuning

Production tuning recommendations:
- Monthly RANGE partitioning by `occurred_at`
- Composite index: `(stream_id, stream_version)`
- Partial index on `event_type` for projection consumers
- `UNLOGGED` tables only for ephemeral projection state, never for events
- Connection pooling: separate pools for commands (small) and queries (larger)

**Confidence**: 0.85

---

## 2. LangGraph in Production (WEB-PY-07 to WEB-PY-12)

### WEB-PY-07: LangGraph Adoption (2025)

LangGraph has become the leading open-source agent orchestration framework:
- Used by companies building production AI agents
- Clear separation from LangSmith (commercial) vs LangGraph (open-source)
- Active development with monthly releases
- Growing ecosystem of checkpointers, tools, and integrations

**Confidence**: 0.85

### WEB-PY-08: Production LangGraph Patterns

Patterns observed in production deployments:
- Keep graph state minimal (references, not data)
- Use subgraphs for complex workflows to manage complexity
- Implement retry logic at the node level, not graph level
- Checkpointer writes add latency; batch state updates where possible
- Monitor graph execution with OpenTelemetry spans per node

**Confidence**: 0.85

### WEB-PY-09: Human-in-the-Loop at Scale

Production patterns for approval gates:
- `interrupt_before` on approval nodes
- Store pending approval metadata in graph state
- External system (Slack) triggers resume via API call
- Timeout handling: scheduled job checks for stale interrupts
- Multiple approvers: collect in state, threshold to proceed

**Confidence**: 0.85

### WEB-PY-10: Multi-Agent Orchestration Lessons

Key lessons from production multi-agent systems (2024-2025):
- Start simple: single agent with tools before multi-agent
- Explicit orchestration (graphs) beats implicit (agent chat)
- Bounded iteration caps prevent runaway costs
- Agent specialization improves output quality
- Shared context window management is critical

**Confidence**: 0.85

### WEB-PY-11: LLM Cost Management

Production cost management strategies:
- Model routing: use cheaper models for simple tasks
- Caching: LLM response cache for repeated queries
- Token budgets per workflow and per agent step
- Prompt optimization: shorter system prompts, structured output
- Cost attribution: tag LLM calls with thread_ref for billing

**Confidence**: 0.85

### WEB-PY-12: Structured Output from LLMs

Best practices for structured LLM output:
- Use model's native structured output (tool calling / JSON mode)
- Pydantic models for output validation
- Retry with error feedback on validation failure
- Discriminated unions for polymorphic outputs
- Avoid regex parsing of free-text output

**Confidence**: 0.90

---

## 3. PII Protection (WEB-PY-13 to WEB-PY-17)

### WEB-PY-13: Presidio in Production

Microsoft Presidio production experiences:
- False negative rate varies by entity type (names: ~15%, emails: ~5%)
- Custom recognizers significantly improve domain-specific detection
- Performance: ~1ms per entity scan, blocking for large texts
- Thread-safe: single `AnalyzerEngine` instance, wrap in `asyncio.to_thread()`

**Confidence**: 0.85

### WEB-PY-14: PII Pipeline Architecture

Recommended architecture:
1. Raw text ingestion (encrypted at rest)
2. Presidio analysis (detect entities)
3. Custom recognizer pass (domain-specific patterns)
4. Confidence threshold check (fail-closed if below threshold)
5. Anonymization with stable per-thread placeholders
6. Emit events: `PIIDetected`, `PIIAnonymised` or `PIIResidualRiskBlocked`
7. Store mapping in encrypted vault

**Confidence**: 0.90

### WEB-PY-15: Stable Placeholder Strategy

For consistent context within a thread:
- Map each unique entity to a deterministic placeholder: `<PERSON_1>`, `<EMAIL_2>`
- Maintain mapping per thread (not per message)
- Store mapping in encrypted vault with thread_ref key
- Reveal requires explicit human action + audit event

**Confidence**: 0.85

### WEB-PY-16: PII in Code

Special considerations for code content:
- Variable names may contain PII (e.g., `john_email`)
- Comments frequently contain PII
- Config files may contain secrets/PII
- Test fixtures often use real-looking data
- Custom recognizers needed for code-specific patterns

**Confidence**: 0.80

### WEB-PY-17: GDPR and Data Residency

Compliance considerations:
- Right to erasure: must be able to purge PII mapping
- Data residency: PII vault location must be configurable per tenant
- Processing records: event trail serves as Article 30 record
- Consent: workspace admin consent at installation time

**Confidence**: 0.80

---

## 4. FastAPI Production Patterns (WEB-PY-18 to WEB-PY-22)

### WEB-PY-18: FastAPI at Scale

Production deployment patterns:
- Uvicorn with `--workers` for multi-process (or Gunicorn + Uvicorn workers)
- Behind reverse proxy (nginx, Traefik) for TLS and load balancing
- Separate process for background workers (event consumers, projections)
- Health endpoints: `/healthz` (liveness), `/readyz` (readiness with DB check)

**Confidence**: 0.90

### WEB-PY-19: Async Pitfalls

Common async mistakes:
- Calling sync code in async handlers (blocks event loop)
- Not using `asyncio.to_thread()` for CPU-bound or sync I/O
- Creating too many concurrent tasks without semaphore
- Missing `await` (returns coroutine object, not result)
- Using `asyncio.sleep()` for polling instead of event-driven patterns

**Confidence**: 0.90

### WEB-PY-20: Structured Logging Best Practices

```python
import structlog

log = structlog.get_logger()
log.info("event_appended",
    event_id=str(event.event_id),
    stream_id=event.stream_id,
    event_type=event.event_type,
    correlation_id=correlation_id,
)
```

Key: correlation_id in every log line. Use `structlog.contextvars` for automatic propagation.

**Confidence**: 0.90

### WEB-PY-21: Dependency Management with uv

`uv` (by Astral) has become the recommended Python package manager:
- 10-100x faster than pip for dependency resolution
- Native lockfile (`uv.lock`) for reproducible builds
- Workspace support for monorepos
- Built-in virtual environment management
- Compatible with `pyproject.toml`

**Confidence**: 0.90

### WEB-PY-22: Python 3.12+ Features

Relevant Python 3.12+ features for Lintel:
- `type` statement for type aliases
- Improved error messages
- Per-interpreter GIL (3.12+, experimental)
- `asyncio.TaskGroup` for structured concurrency
- `tomllib` for TOML config reading

**Confidence**: 0.85
