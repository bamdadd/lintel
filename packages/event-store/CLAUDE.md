# lintel-event-store

Append-only event store with optimistic concurrency and hash chaining — Postgres and in-memory backends.

## Key exports

- `PostgresEventStore` — Postgres-backed event store; appends `EventEnvelope` with version checks, publishes to `EventBus` after commit
- `InMemoryEventStore` — Dict-backed store with monotonic `global_position`; for tests and dev
- `OptimisticConcurrencyError` — raised when `expected_version` does not match stream head
- `run_migrations` (in `migrate.py`) — applies DDL to create the `events` table

## Dependencies

- `lintel-contracts` — `EventEnvelope`, `EventBus` protocol, `EVENT_TYPE_MAP`
- `asyncpg>=0.30`, `structlog>=24.4`

## Tests

```bash
make test-event-store
# or: uv run pytest packages/event-store/tests/ -v
```

## Usage

```python
from lintel.event_store.postgres import PostgresEventStore
from lintel.event_store.in_memory import InMemoryEventStore

store = PostgresEventStore(pool, event_bus=bus)
await store.append("thread:ws:ch:ts", [envelope], expected_version=-1)
events = await store.read_stream("thread:ws:ch:ts")
```
