# lintel-projections

Event-driven read-model projections with reactive engine, snapshot persistence, and catch-up replay.

## Key exports

- `InMemoryProjectionEngine` — dispatches events to registered `Projection` instances; subscribes to `EventBus` for live delivery; snapshots state to `ProjectionStore` every N events; replays on `start()` via catch-up
- `InMemoryProjectionStore` — dict-backed projection state store for tests (in `stores.py`)
- `PostgresProjectionStore` — Postgres-backed projection state store with JSONB (in `stores.py`)
- `AuditProjection` (in `audit.py`) — builds audit trail from state-change events into `AuditStore`
- `ThreadStatusProjection` (in `thread_status.py`) — maintains in-memory thread status view from `ThreadMessageReceived`, `WorkflowStarted`, `WorkflowAdvanced` events
- `QualityMetricsProjection` (in `quality_metrics.py`) — aggregates test coverage delta, defect density, and rework ratio over rolling windows
- `TaskBacklogProjection` (in `task_backlog.py`) — maintains ordered task backlog view

## Dependencies

- `lintel-contracts` — `Projection`, `ProjectionStore`, `ProjectionState`, `EventBus`, `EventStore` protocols
- `lintel-event-bus`, `asyncpg>=0.30`, `structlog>=24.4`

## Tests

```bash
make test-projections
# or: uv run pytest packages/projections/tests/ -v
```

## Usage

```python
from lintel.projections.engine import InMemoryProjectionEngine
from lintel.projections.thread_status import ThreadStatusProjection

engine = InMemoryProjectionEngine(event_bus=bus, event_store=store)
engine.register(ThreadStatusProjection(status_store))
await engine.start()
```
