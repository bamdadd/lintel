# Projection Infrastructure Design

Extract shared projection infrastructure for event-driven computations.

## Problem

Multiple features need the same pattern: subscribe to events, maintain running aggregates, persist state, rebuild from history. MET-1, MET-6, GRD-1, 034.2 will each build this independently if we don't extract it now.

## Current State

- `Projection` Protocol in `packages/domain/src/lintel/domain/projections/protocols.py` with `handled_event_types`, `project(event)`, `rebuild(events)`
- `ProjectionEngine` Protocol alongside it with `register()`, `project()`, `rebuild_all()`
- `InMemoryProjectionEngine` in `packages/infrastructure/src/lintel/infrastructure/projections/engine.py` — dispatches events to projections, subscribes to EventBus, supports `reset_all()` and `rebuild_all(stream_id)`
- Four concrete projections: TaskBacklog, ThreadStatus, Audit, QualityMetrics — all in-memory, no position tracking, no persistence
- `EventEnvelope` has `global_position` (auto-assigned monotonic int)
- `EventStore.read_all(from_position, limit)` supports catch-up reads
- `catch_up_subscribe()` in `event_bus/subscriptions.py` handles gap-free replay with buffering

## What's Missing

- No position tracking — projections can't resume from where they left off
- No state persistence — all projection state lost on restart
- No health visibility — no way to see projection status or lag
- No snapshot/restore lifecycle

## Design

### Data Model

```python
@dataclass(frozen=True)
class ProjectionState:
    """Persisted state of a projection."""
    projection_name: str
    global_position: int          # last processed global position
    stream_position: int | None   # last processed stream version (None for log-wide)
    state: dict[str, Any]         # serialised projection state
    updated_at: datetime
```

**Package:** `packages/contracts/src/lintel/contracts/projections.py`

### Projection Protocol Changes

Extend the existing `Projection` Protocol with two new members:

```python
class Projection(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def handled_event_types(self) -> set[str]: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild(self, events: list[EventEnvelope]) -> None: ...

    def get_state(self) -> dict[str, Any]: ...

    def restore_state(self, state: dict[str, Any]) -> None: ...
```

New members:
- `name` — unique identifier for the projection (e.g. `"task_backlog"`)
- `get_state()` — serialise current in-memory state to a dict
- `restore_state(state)` — restore from a previously serialised dict

Existing projections gain these three members. `get_state()` returns their internal dict. `restore_state()` replaces it.

**Package:** remains in `packages/domain/src/lintel/domain/projections/protocols.py`

### ProjectionStore Protocol

```python
class ProjectionStore(Protocol):
    async def save(self, state: ProjectionState) -> None: ...
    async def load(self, projection_name: str) -> ProjectionState | None: ...
    async def load_all(self) -> list[ProjectionState]: ...
    async def delete(self, projection_name: str) -> None: ...
```

**Package:** `packages/domain/src/lintel/domain/projections/protocols.py` (alongside Projection)

### InMemoryProjectionStore

Dict-backed implementation for tests.

```python
class InMemoryProjectionStore:
    def __init__(self) -> None:
        self._states: dict[str, ProjectionState] = {}

    async def save(self, state: ProjectionState) -> None:
        self._states[state.projection_name] = state

    async def load(self, projection_name: str) -> ProjectionState | None:
        return self._states.get(projection_name)

    async def load_all(self) -> list[ProjectionState]:
        return list(self._states.values())

    async def delete(self, projection_name: str) -> None:
        self._states.pop(projection_name, None)
```

**Package:** `packages/infrastructure/src/lintel/infrastructure/projections/stores.py`

### PostgresProjectionStore

Uses the existing JSONB entities table pattern (`PostgresDictStore`) with `kind="projection_state"` and `entity_id=projection_name`.

```python
class PostgresProjectionStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._inner = PostgresDictStore(pool, kind="projection_state")

    async def save(self, state: ProjectionState) -> None:
        data = asdict(state)
        data["updated_at"] = data["updated_at"].isoformat()
        await self._inner.put(state.projection_name, data)

    async def load(self, projection_name: str) -> ProjectionState | None:
        data = await self._inner.get(projection_name)
        if data is None:
            return None
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return ProjectionState(**data)

    async def load_all(self) -> list[ProjectionState]:
        rows = await self._inner.list_all()
        for r in rows:
            r["updated_at"] = datetime.fromisoformat(r["updated_at"])
        return [ProjectionState(**r) for r in rows]

    async def delete(self, projection_name: str) -> None:
        await self._inner.remove(projection_name)
```

**Package:** `packages/infrastructure/src/lintel/infrastructure/projections/stores.py`

### ProjectionEngine Changes

Extend `InMemoryProjectionEngine` to support position tracking, persistence, and health.

**New constructor params:**
- `projection_store: ProjectionStore | None` — for persistence
- `snapshot_interval: int = 100` — save state every N events

**New behaviour:**
- `_positions: dict[str, int]` — tracks `global_position` per projection name
- On `start()`: load persisted state for each projection via `projection_store.load()`, call `projection.restore_state()`, set position
- On `project(event)`: after dispatching, increment position. Every `snapshot_interval` events, persist via `projection_store.save()`
- `get_status() -> list[ProjectionStatus]` — returns name, status, position, lag for each projection

**Position-aware catch-up:**
- On `start()`, after restoring state, use `catch_up_subscribe(event_bus, event_store, handler, from_position=last_position + 1)` from `event_bus/subscriptions.py`
- This handles gap-free replay with buffering and deduplication — subscribes to live events first, replays historical, then drains the buffer. Eliminates the race condition window of manual read-then-subscribe.
- No need to separately subscribe to EventBus afterward; `catch_up_subscribe` does both.

**Graceful shutdown:**
- `stop()` persists final state for all projections before unsubscribing, so at most 0 events are lost on clean shutdown. The `snapshot_interval` trade-off (up to N-1 events lost) only applies to crashes.

```python
@dataclass(frozen=True)
class ProjectionStatus:
    name: str
    status: str            # "running" | "catching_up" | "stopped" | "error"
    global_position: int
    lag: int               # head_position - projection_position
    last_event_at: datetime | None
    events_processed: int
```

**Package:** `ProjectionStatus` in contracts. Engine changes in existing `engine.py`.

### ProjectionEngine Protocol Update

**Breaking change:** The existing Protocol only has `register`, `project`, `rebuild_all`. Adding `start`, `stop`, `get_status`, `reset_all` means any external implementors must update. The existing `InMemoryProjectionEngine` already implements `start`, `stop`, `reset_all` so the only truly new method is `get_status`.

```python
class ProjectionEngine(Protocol):
    async def register(self, projection: Projection) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def project(self, event: EventEnvelope) -> None: ...
    async def rebuild_all(self, stream_id: str) -> None: ...
    async def get_status(self) -> list[ProjectionStatus]: ...
    async def reset_all(self) -> None: ...
```

### Health Endpoint

```
GET /admin/projections
```

Returns:
```json
[
  {
    "name": "task_backlog",
    "status": "running",
    "global_position": 4521,
    "lag": 3,
    "last_event_at": "2026-03-14T10:30:00Z",
    "events_processed": 4521
  }
]
```

**Implementation:** New route in `packages/app/src/lintel/api/routes/admin.py` that calls `engine.get_status()`. Uses existing `get_projection_engine` dependency pattern (not `Provide[AppContainer.X]`) to match the other admin routes.

### Existing Projection Migration

Each of the four existing projections gains three new members:

| Projection | `name` | `get_state()` returns | `restore_state()` replaces |
|---|---|---|---|
| TaskBacklogProjection | `"task_backlog"` | `self._tasks` | `self._tasks` |
| ThreadStatusProjection | `"thread_status"` | `self._threads` | `self._threads` |
| AuditProjection | `"audit"` | `{}` (stateless, writes to store) | no-op |
| QualityMetricsProjection | `"quality_metrics"` | `self._metrics` | `self._metrics` |

AuditProjection is effectively stateless (it writes to an external store), so `get_state()` returns empty dict and `restore_state()` is a no-op.

### Wiring

In `packages/app/src/lintel/api/app.py` lifespan:
1. Create `PostgresProjectionStore(pool)` (or `InMemoryProjectionStore` for tests)
2. Pass to `InMemoryProjectionEngine(event_store, event_bus, projection_store)`
3. `engine.start()` loads state, catches up, subscribes to live events
4. Wire `projection_store` into `AppContainer`

### MCP Tool

Add `admin_get_projection_status` tool to the MCP server that calls `GET /admin/projections`.

Already exists: `admin_reset_projections` — this continues to work via `engine.reset_all()`, which now also clears persisted state.

## File Changes Summary

| File | Change |
|---|---|
| `packages/contracts/src/lintel/contracts/projections.py` | **New.** `ProjectionState`, `ProjectionStatus` dataclasses |
| `packages/domain/src/lintel/domain/projections/protocols.py` | Add `name`, `get_state()`, `restore_state()` to Projection. Add `ProjectionStore` protocol. Update `ProjectionEngine` protocol. |
| `packages/infrastructure/src/lintel/infrastructure/projections/stores.py` | **New.** `InMemoryProjectionStore`, `PostgresProjectionStore` |
| `packages/infrastructure/src/lintel/infrastructure/projections/engine.py` | Add position tracking, persistence, catch-up, `get_status()` |
| `packages/infrastructure/src/lintel/infrastructure/projections/task_backlog.py` | Add `name`, `get_state()`, `restore_state()` |
| `packages/infrastructure/src/lintel/infrastructure/projections/thread_status.py` | Add `name`, `get_state()`, `restore_state()` |
| `packages/infrastructure/src/lintel/infrastructure/projections/audit.py` | Add `name`, `get_state()`, `restore_state()` (no-op) |
| `packages/infrastructure/src/lintel/infrastructure/projections/quality_metrics.py` | Add `name`, `get_state()`, `restore_state()` |
| `packages/app/src/lintel/api/routes/admin.py` | Add `GET /admin/projections` endpoint |
| `packages/app/src/lintel/api/app.py` | Wire `ProjectionStore` into engine and container |

## Tests

| Test | Package | What |
|---|---|---|
| `test_projection_store.py` | infrastructure | `InMemoryProjectionStore` and `PostgresProjectionStore` CRUD |
| `test_projection_engine_persistence.py` | infrastructure | Engine saves/restores state, catches up from position |
| `test_projection_status.py` | infrastructure | `get_status()` returns correct lag and status |
| `test_projection_migration.py` | infrastructure | Existing projections implement `name`, `get_state()`, `restore_state()` |
| `test_admin_projections.py` | app | `GET /admin/projections` returns expected JSON |

## Dependencies

- **Depends on:** EVT-2 (catch-up subscriptions) — already implemented in `subscriptions.py`
- **Blocks:** MET-1, MET-6, GRD-1, GRD-7, 034.2, 034.4.3
