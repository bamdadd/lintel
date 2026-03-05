# Clean Code Analysis - Python Backend

## Standards for Lintel's Python Backend with Event Sourcing

---

## 1. Architecture Principles

### CLEAN-PY-01: Hexagonal Architecture
Strict concentric layers with inward-only dependencies: `domain/` (pure logic) -> `application/` (use cases) -> `infrastructure/` (adapters) -> `api/` (delivery). Enforce with import linting.

### CLEAN-PY-02: Domain-Driven Service Boundaries
Bounded contexts: Agent Runtime (`AgentSession`), Workflow Engine (`Workflow`), Collaboration (`Conversation`), Sandbox (`SandboxInstance`). Cross-context communication via domain events only.

### CLEAN-PY-03: Dependency Inversion via Protocols
Every external capability defined as a `Protocol` in the domain layer. Infrastructure provides implementations via structural subtyping.

### CLEAN-PY-04: CQRS with Event Sourcing
Separate write path (commands -> events) from read path (projections -> queries). Command handlers produce events; projections consume them.

---

## 2. Python-Specific Standards

### CLEAN-PY-05: Typed Models Everywhere
Domain models: `dataclass(frozen=True)`. API boundary: Pydantic. Never use Pydantic inside the domain layer.

### CLEAN-PY-06: Async-First Design
All I/O-bound operations async. CPU-bound work in executors. Never block the event loop. Wrap Presidio with `asyncio.to_thread()`.

### CLEAN-PY-07: FastAPI Dependency Injection
Use `Depends()` with factory functions. Never instantiate infrastructure in route handlers.

### CLEAN-PY-08: Exception Hierarchies
Domain exceptions carry business meaning. Infrastructure exceptions translated at boundaries. FastAPI handlers map domain exceptions to HTTP responses.

### CLEAN-PY-09: Testing Patterns
Domain tests: synchronous, pure, no mocks. Infrastructure tests: real backends via testcontainers. Async fixtures with `pytest-asyncio`.

---

## 3. Event Sourcing Standards

### CLEAN-PY-10: Immutable Events
Always `frozen=True`, `tuple` not `list`, every event carries `event_id`, `occurred_at`, `schema_version`. Past-tense naming.

### CLEAN-PY-11: Event Versioning
Upcasters transform old event shapes to current. Never modify stored events. Version in type name: `PIIDetected.v1`.

### CLEAN-PY-12: Projection Rebuilds
Projections are disposable read models, rebuildable from events. Never treat a projection as source of truth.

### CLEAN-PY-13: Idempotency
Every handler idempotent. Use event IDs for deduplication. HTTP APIs use idempotency keys.

### CLEAN-PY-14: Command/Event Separation
Commands express intent (imperative, may fail). Events record facts (past tense, never rejected).

---

## 4. Anti-Patterns

### CLEAN-PY-15: No God Classes
Decompose into focused collaborators: `AgentSession`, `ToolRouter`, `StreamingAccumulator`, `ConversationMemory`.

### CLEAN-PY-16: No Infrastructure in Domain
Domain layer has zero imports from infrastructure.

### CLEAN-PY-17: No Tight Coupling Between Services
Cross-service communication via events only.

### CLEAN-PY-18: Event Schema Validation
Registry-check all deserialized events. Unknown types raise exceptions.

### CLEAN-PY-19: No Sync Blocking in Async Code
Ban `requests`, `time.sleep()`, sync DB drivers. Use `httpx`, `asyncio.sleep()`, `asyncpg`.

### CLEAN-PY-20: Naming Conventions
Events: past tense. Commands: imperative. Protocols: nouns. Handlers: `handle_<command>` or `on_<event>`. No abbreviations.
