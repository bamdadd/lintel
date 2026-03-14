# lintel-coordination

PostgreSQL advisory lock coordinator for single-scheduler-per-tick guarantees.

## Key exports

- `AdvisoryLockCoordinator` — acquires/releases Postgres session-level advisory locks; uses `pg_try_advisory_lock` (non-blocking) with a fixed `SCHEDULER_LOCK_ID = 42424242`; ensures only one scheduler tick runs at a time across replicas

## Dependencies

- `asyncpg>=0.30` (no lintel-contracts dependency)

## Tests

```bash
make test-coordination
# or: uv run pytest packages/coordination/tests/ -v
```

## Usage

```python
from lintel.coordination.advisory_lock import AdvisoryLockCoordinator

coord = AdvisoryLockCoordinator(pool)
if await coord.try_acquire_scheduler_lock():
    try:
        await run_scheduler_tick()
    finally:
        await coord.release_scheduler_lock()
```
