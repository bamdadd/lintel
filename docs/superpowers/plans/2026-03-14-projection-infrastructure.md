# Projection Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract shared projection infrastructure with position tracking, state persistence, catch-up subscriptions, and a health endpoint.

**Architecture:** Extend existing `Projection` Protocol with `name`/`get_state`/`restore_state`. Add `ProjectionStore` protocol with in-memory and Postgres implementations. Enhance `InMemoryProjectionEngine` with position tracking, periodic persistence, and catch-up via existing `catch_up_subscribe`. Add `GET /admin/projections` health endpoint.

**Tech Stack:** Python 3.12+, asyncpg, pytest, frozen dataclasses, PostgresDictStore pattern

**Spec:** `docs/superpowers/specs/2026-03-14-projection-infrastructure-design.md`

---

## Chunk 1: Data Models & Protocols

### Task 1: ProjectionState and ProjectionStatus dataclasses

**Files:**
- Create: `packages/contracts/src/lintel/contracts/projections.py`
- Test: `packages/contracts/tests/test_projections.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/contracts/tests/test_projections.py
"""Tests for projection data models."""

from datetime import UTC, datetime

from lintel.contracts.projections import ProjectionState, ProjectionStatus


class TestProjectionState:
    def test_create_projection_state(self) -> None:
        state = ProjectionState(
            projection_name="task_backlog",
            global_position=42,
            stream_position=None,
            state={"tasks": {"abc": {"status": "pending"}}},
            updated_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
        )
        assert state.projection_name == "task_backlog"
        assert state.global_position == 42
        assert state.stream_position is None
        assert state.state == {"tasks": {"abc": {"status": "pending"}}}

    def test_projection_state_is_frozen(self) -> None:
        state = ProjectionState(
            projection_name="test",
            global_position=0,
            stream_position=None,
            state={},
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        try:
            state.projection_name = "other"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass

    def test_stream_position_optional(self) -> None:
        state = ProjectionState(
            projection_name="test",
            global_position=10,
            stream_position=5,
            state={},
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert state.stream_position == 5


class TestProjectionStatus:
    def test_create_projection_status(self) -> None:
        status = ProjectionStatus(
            name="task_backlog",
            status="running",
            global_position=100,
            lag=3,
            last_event_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            events_processed=100,
        )
        assert status.name == "task_backlog"
        assert status.status == "running"
        assert status.lag == 3
        assert status.events_processed == 100

    def test_last_event_at_nullable(self) -> None:
        status = ProjectionStatus(
            name="empty",
            status="stopped",
            global_position=0,
            lag=0,
            last_event_at=None,
            events_processed=0,
        )
        assert status.last_event_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_projections.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lintel.contracts.projections'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/contracts/src/lintel/contracts/projections.py
"""Projection data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ProjectionState:
    """Persisted state of a projection."""

    projection_name: str
    global_position: int
    stream_position: int | None
    state: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True)
class ProjectionStatus:
    """Runtime status of a projection for health reporting."""

    name: str
    status: str  # "running" | "catching_up" | "stopped" | "error"
    global_position: int
    lag: int
    last_event_at: datetime | None
    events_processed: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_projections.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/lintel/contracts/projections.py packages/contracts/tests/test_projections.py
git commit -m "feat: add ProjectionState and ProjectionStatus data models"
```

### Task 2: Update Projection and ProjectionEngine protocols, add ProjectionStore protocol

**Files:**
- Modify: `packages/domain/src/lintel/domain/projections/protocols.py`
- Test: `packages/domain/tests/domain/test_projection_protocols.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/domain/tests/domain/test_projection_protocols.py
"""Tests that verify Protocol structural compliance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.projections import ProjectionState, ProjectionStatus
from lintel.domain.projections.protocols import (
    Projection,
    ProjectionEngine,
    ProjectionStore,
)


class FakeProjection:
    """Minimal implementation to verify Protocol shape."""

    @property
    def name(self) -> str:
        return "fake"

    @property
    def handled_event_types(self) -> set[str]:
        return {"TestEvent"}

    async def project(self, event: EventEnvelope) -> None:
        pass

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        pass

    def get_state(self) -> dict[str, Any]:
        return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        pass


class FakeProjectionStore:
    """Minimal implementation to verify Protocol shape."""

    async def save(self, state: ProjectionState) -> None:
        pass

    async def load(self, projection_name: str) -> ProjectionState | None:
        return None

    async def load_all(self) -> list[ProjectionState]:
        return []

    async def delete(self, projection_name: str) -> None:
        pass


class FakeProjectionEngine:
    """Minimal implementation to verify Protocol shape."""

    async def register(self, projection: Projection) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def project(self, event: EventEnvelope) -> None:
        pass

    async def rebuild_all(self, stream_id: str) -> None:
        pass

    async def get_status(self) -> list[ProjectionStatus]:
        return []

    async def reset_all(self) -> None:
        pass


def test_fake_projection_satisfies_protocol() -> None:
    p: Projection = FakeProjection()
    assert p.name == "fake"
    assert p.handled_event_types == {"TestEvent"}
    assert p.get_state() == {}


def test_fake_store_satisfies_protocol() -> None:
    s: ProjectionStore = FakeProjectionStore()
    assert s is not None


def test_fake_engine_satisfies_protocol() -> None:
    e: ProjectionEngine = FakeProjectionEngine()
    assert e is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/domain/tests/domain/test_projection_protocols.py -v`
Expected: FAIL — `ProjectionStore` not importable, `Projection` missing `name`/`get_state`/`restore_state`

- [ ] **Step 3: Write minimal implementation**

Replace the entire contents of `packages/domain/src/lintel/domain/projections/protocols.py`:

```python
"""Projection protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.projections import ProjectionState, ProjectionStatus


class Projection(Protocol):
    """A projection that builds a read model from events."""

    @property
    def name(self) -> str: ...

    @property
    def handled_event_types(self) -> set[str]: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild(self, events: list[EventEnvelope]) -> None: ...

    def get_state(self) -> dict[str, Any]: ...

    def restore_state(self, state: dict[str, Any]) -> None: ...


class ProjectionStore(Protocol):
    """Persists projection state for recovery after restart."""

    async def save(self, state: ProjectionState) -> None: ...

    async def load(self, projection_name: str) -> ProjectionState | None: ...

    async def load_all(self) -> list[ProjectionState]: ...

    async def delete(self, projection_name: str) -> None: ...


class ProjectionEngine(Protocol):
    """Dispatches events to registered projections."""

    async def register(self, projection: Projection) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild_all(self, stream_id: str) -> None: ...

    async def get_status(self) -> list[ProjectionStatus]: ...

    async def reset_all(self) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/domain/tests/domain/test_projection_protocols.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/domain/src/lintel/domain/projections/protocols.py packages/domain/tests/domain/test_projection_protocols.py
git commit -m "feat: extend Projection protocol with name/get_state/restore_state, add ProjectionStore protocol"
```

---

## Chunk 2: Projection Stores

### Task 3: InMemoryProjectionStore

**Files:**
- Create: `packages/infrastructure/src/lintel/infrastructure/projections/stores.py`
- Test: `packages/infrastructure/tests/projections/test_projection_stores.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/infrastructure/tests/projections/test_projection_stores.py
"""Tests for InMemoryProjectionStore."""

from datetime import UTC, datetime

from lintel.contracts.projections import ProjectionState
from lintel.infrastructure.projections.stores import InMemoryProjectionStore


def _make_state(name: str = "test", position: int = 0) -> ProjectionState:
    return ProjectionState(
        projection_name=name,
        global_position=position,
        stream_position=None,
        state={"key": "value"},
        updated_at=datetime(2026, 3, 14, tzinfo=UTC),
    )


class TestInMemoryProjectionStore:
    async def test_save_and_load(self) -> None:
        store = InMemoryProjectionStore()
        state = _make_state("backlog", 42)
        await store.save(state)
        loaded = await store.load("backlog")
        assert loaded == state

    async def test_load_missing_returns_none(self) -> None:
        store = InMemoryProjectionStore()
        assert await store.load("missing") is None

    async def test_save_overwrites(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a", 1))
        await store.save(_make_state("a", 2))
        loaded = await store.load("a")
        assert loaded is not None
        assert loaded.global_position == 2

    async def test_load_all(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a", 1))
        await store.save(_make_state("b", 2))
        all_states = await store.load_all()
        assert len(all_states) == 2
        names = {s.projection_name for s in all_states}
        assert names == {"a", "b"}

    async def test_delete(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a"))
        await store.delete("a")
        assert await store.load("a") is None

    async def test_delete_missing_is_noop(self) -> None:
        store = InMemoryProjectionStore()
        await store.delete("nope")  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/infrastructure/tests/projections/test_projection_stores.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/infrastructure/src/lintel/infrastructure/projections/stores.py
"""Projection state stores — in-memory and Postgres implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.projections import ProjectionState


class InMemoryProjectionStore:
    """Dict-backed projection store for testing."""

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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/infrastructure/tests/projections/test_projection_stores.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/projections/stores.py packages/infrastructure/tests/projections/test_projection_stores.py
git commit -m "feat: add InMemoryProjectionStore"
```

### Task 4: PostgresProjectionStore

**Files:**
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/stores.py`
- Test: `packages/infrastructure/tests/projections/test_postgres_projection_store.py`

This test requires a running Postgres instance (testcontainers or dev DB). Mark as integration test.

- [ ] **Step 1: Write the failing test**

```python
# packages/infrastructure/tests/projections/test_postgres_projection_store.py
"""Integration tests for PostgresProjectionStore.

Requires a running Postgres instance. Uses the shared test fixtures from
conftest.py for pool setup.
"""

import pytest
from datetime import UTC, datetime

from lintel.contracts.projections import ProjectionState
from lintel.infrastructure.projections.stores import PostgresProjectionStore


def _make_state(name: str = "test", position: int = 0) -> ProjectionState:
    return ProjectionState(
        projection_name=name,
        global_position=position,
        stream_position=None,
        state={"tasks": {"abc": {"status": "pending"}}},
        updated_at=datetime(2026, 3, 14, 10, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def store(pg_pool: "asyncpg.Pool") -> PostgresProjectionStore:
    return PostgresProjectionStore(pg_pool)


@pytest.mark.integration
class TestPostgresProjectionStore:
    async def test_save_and_load(self, store: PostgresProjectionStore) -> None:
        state = _make_state("backlog", 42)
        await store.save(state)
        loaded = await store.load("backlog")
        assert loaded is not None
        assert loaded.projection_name == "backlog"
        assert loaded.global_position == 42
        assert loaded.state == {"tasks": {"abc": {"status": "pending"}}}
        assert loaded.updated_at == datetime(2026, 3, 14, 10, 30, 0, tzinfo=UTC)

    async def test_load_missing(self, store: PostgresProjectionStore) -> None:
        assert await store.load("nope") is None

    async def test_save_overwrites(self, store: PostgresProjectionStore) -> None:
        await store.save(_make_state("a", 1))
        await store.save(_make_state("a", 2))
        loaded = await store.load("a")
        assert loaded is not None
        assert loaded.global_position == 2

    async def test_load_all(self, store: PostgresProjectionStore) -> None:
        await store.save(_make_state("x", 10))
        await store.save(_make_state("y", 20))
        all_states = await store.load_all()
        names = {s.projection_name for s in all_states}
        assert {"x", "y"}.issubset(names)

    async def test_delete(self, store: PostgresProjectionStore) -> None:
        await store.save(_make_state("del"))
        await store.delete("del")
        assert await store.load("del") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/infrastructure/tests/projections/test_postgres_projection_store.py -v -m integration`
Expected: FAIL — `PostgresProjectionStore` not defined

- [ ] **Step 3: Write minimal implementation**

Append to `packages/infrastructure/src/lintel/infrastructure/projections/stores.py`:

```python
import json
from dataclasses import asdict
from datetime import datetime

if TYPE_CHECKING:
    import asyncpg


class PostgresProjectionStore:
    """Postgres-backed projection store using the shared entities table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.infrastructure.persistence.dict_store import PostgresDictStore

        self._inner = PostgresDictStore(pool, kind="projection_state")

    async def save(self, state: ProjectionState) -> None:
        data = asdict(state)
        data["updated_at"] = data["updated_at"].isoformat()
        await self._inner.put(state.projection_name, data)

    async def load(self, projection_name: str) -> ProjectionState | None:
        from lintel.contracts.projections import ProjectionState as PS

        data = await self._inner.get(projection_name)
        if data is None:
            return None
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return PS(**data)

    async def load_all(self) -> list[ProjectionState]:
        from lintel.contracts.projections import ProjectionState as PS

        rows = await self._inner.list_all()
        for r in rows:
            r["updated_at"] = datetime.fromisoformat(r["updated_at"])
        return [PS(**r) for r in rows]

    async def delete(self, projection_name: str) -> None:
        await self._inner.remove(projection_name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/infrastructure/tests/projections/test_postgres_projection_store.py -v -m integration`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/projections/stores.py packages/infrastructure/tests/projections/test_postgres_projection_store.py
git commit -m "feat: add PostgresProjectionStore"
```

---

## Chunk 3: Migrate Existing Projections

### Task 5: Add name/get_state/restore_state to all four existing projections

**Files:**
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/task_backlog.py`
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/thread_status.py`
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/audit.py`
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/quality_metrics.py`
- Test: `packages/infrastructure/tests/projections/test_projection_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/infrastructure/tests/projections/test_projection_migration.py
"""Tests that all existing projections implement the extended Projection protocol."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.infrastructure.projections.task_backlog import TaskBacklogProjection
from lintel.infrastructure.projections.thread_status import ThreadStatusProjection
from lintel.infrastructure.projections.audit import AuditProjection
from lintel.infrastructure.projections.quality_metrics import QualityMetricsProjection


class TestTaskBacklogProjectionProtocol:
    def test_has_name(self) -> None:
        p = TaskBacklogProjection()
        assert p.name == "task_backlog"

    def test_get_state_returns_dict(self) -> None:
        p = TaskBacklogProjection()
        assert p.get_state() == {}

    def test_restore_state_replaces_internal(self) -> None:
        p = TaskBacklogProjection()
        p.restore_state({"abc": {"status": "pending"}})
        assert p.get_state() == {"abc": {"status": "pending"}}
        assert p.get_backlog() == [{"status": "pending"}]

    def test_get_state_roundtrips(self) -> None:
        p = TaskBacklogProjection()
        p.restore_state({"x": {"status": "done"}})
        state = p.get_state()
        p2 = TaskBacklogProjection()
        p2.restore_state(state)
        assert p2.get_state() == state


class TestThreadStatusProjectionProtocol:
    def test_has_name(self) -> None:
        p = ThreadStatusProjection()
        assert p.name == "thread_status"

    def test_get_state_roundtrips(self) -> None:
        p = ThreadStatusProjection()
        p.restore_state({"t1": {"status": "active"}})
        state = p.get_state()
        p2 = ThreadStatusProjection()
        p2.restore_state(state)
        assert p2.get_all() == [{"status": "active"}]


class TestAuditProjectionProtocol:
    def test_has_name(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        assert p.name == "audit"

    def test_get_state_returns_empty(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        assert p.get_state() == {}

    def test_restore_state_is_noop(self) -> None:
        p = AuditProjection(audit_store=AsyncMock())
        p.restore_state({"anything": True})  # should not raise
        assert p.get_state() == {}


class TestQualityMetricsProjectionProtocol:
    def test_has_name(self) -> None:
        p = QualityMetricsProjection()
        assert p.name == "quality_metrics"

    def test_get_state_returns_dict(self) -> None:
        p = QualityMetricsProjection()
        state = p.get_state()
        assert "coverage_records" in state
        assert "defect_records" in state
        assert "commit_records" in state
        assert "merge_records" in state

    def test_restore_state_roundtrips(self) -> None:
        p = QualityMetricsProjection()
        state = p.get_state()
        p2 = QualityMetricsProjection()
        p2.restore_state(state)
        assert p2.get_state() == state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/infrastructure/tests/projections/test_projection_migration.py -v`
Expected: FAIL — `AttributeError: 'TaskBacklogProjection' object has no attribute 'name'`

- [ ] **Step 3: Implement — TaskBacklogProjection**

Add to `packages/infrastructure/src/lintel/infrastructure/projections/task_backlog.py`, inside the class after `__init__`:

```python
    @property
    def name(self) -> str:
        return "task_backlog"

    def get_state(self) -> dict[str, Any]:
        return dict(self._tasks)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tasks = dict(state)
```

- [ ] **Step 4: Implement — ThreadStatusProjection**

Add to `packages/infrastructure/src/lintel/infrastructure/projections/thread_status.py`, inside the class after `__init__`:

```python
    @property
    def name(self) -> str:
        return "thread_status"

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)
```

- [ ] **Step 5: Implement — AuditProjection**

Add to `packages/infrastructure/src/lintel/infrastructure/projections/audit.py`, inside the class after `__init__`:

```python
    @property
    def name(self) -> str:
        return "audit"

    def get_state(self) -> dict[str, Any]:
        return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        pass
```

- [ ] **Step 6: Implement — QualityMetricsProjection**

Add to `packages/infrastructure/src/lintel/infrastructure/projections/quality_metrics.py`, inside the class after `__init__`. The internal state uses dataclass records, so serialize them:

```python
    @property
    def name(self) -> str:
        return "quality_metrics"

    def get_state(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "coverage_records": [asdict(r) for r in self._coverage_records],
            "defect_records": [asdict(r) for r in self._defect_records],
            "commit_records": [asdict(r) for r in self._commit_records],
            "merge_records": [asdict(r) for r in self._merge_records],
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        from datetime import datetime

        def _parse_dt(v: Any) -> datetime:
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        self._coverage_records = [
            CoverageRecord(
                project_id=r["project_id"],
                commit_sha=r["commit_sha"],
                pr_id=r["pr_id"],
                coverage_before=r["coverage_before"],
                coverage_after=r["coverage_after"],
                occurred_at=_parse_dt(r["occurred_at"]),
            )
            for r in state.get("coverage_records", [])
        ]
        self._defect_records = [
            DefectRecord(
                project_id=r["project_id"],
                work_item_id=r["work_item_id"],
                occurred_at=_parse_dt(r["occurred_at"]),
            )
            for r in state.get("defect_records", [])
        ]
        self._commit_records = [
            CommitRecord(
                project_id=r["project_id"],
                commit_sha=r["commit_sha"],
                lines_changed=r["lines_changed"],
                files=r["files"],
                occurred_at=_parse_dt(r["occurred_at"]),
            )
            for r in state.get("commit_records", [])
        ]
        self._merge_records = [
            MergeRecord(
                project_id=r["project_id"],
                pr_id=r["pr_id"],
                files=r["files"],
                occurred_at=_parse_dt(r["occurred_at"]),
            )
            for r in state.get("merge_records", [])
        ]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/infrastructure/tests/projections/test_projection_migration.py -v`
Expected: PASS (all 11 tests)

- [ ] **Step 8: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/projections/task_backlog.py packages/infrastructure/src/lintel/infrastructure/projections/thread_status.py packages/infrastructure/src/lintel/infrastructure/projections/audit.py packages/infrastructure/src/lintel/infrastructure/projections/quality_metrics.py packages/infrastructure/tests/projections/test_projection_migration.py
git commit -m "feat: add name/get_state/restore_state to all existing projections"
```

---

## Chunk 4: Engine Enhancement

### Task 6: Add position tracking, persistence, catch-up, and get_status to InMemoryProjectionEngine

**Files:**
- Modify: `packages/infrastructure/src/lintel/infrastructure/projections/engine.py`
- Test: `packages/infrastructure/tests/projections/test_engine_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/infrastructure/tests/projections/test_engine_persistence.py
"""Tests for ProjectionEngine position tracking, persistence, and status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.projections import ProjectionState
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.stores import InMemoryProjectionStore


class StubProjection:
    """Minimal projection for testing engine behaviour."""

    def __init__(self, projection_name: str = "stub") -> None:
        self._name = projection_name
        self._events: list[EventEnvelope] = []
        self._state: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def handled_event_types(self) -> set[str]:
        return {"TestEvent"}

    async def project(self, event: EventEnvelope) -> None:
        self._events.append(event)
        self._state[str(event.event_id)] = event.event_type

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._events.clear()
        self._state.clear()
        for e in events:
            await self.project(e)

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)


def _make_event(position: int = 0) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type="TestEvent",
        schema_version=1,
        occurred_at=datetime.now(UTC),
        actor_type="system",
        actor_id="test",
        thread_ref=None,
        correlation_id=uuid4(),
        causation_id=uuid4(),
        payload={},
        idempotency_key=None,
        global_position=position,
    )


class TestEnginePositionTracking:
    async def test_position_starts_at_zero(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        statuses = await engine.get_status()
        assert len(statuses) == 1
        assert statuses[0].global_position == 0
        assert statuses[0].events_processed == 0

    async def test_position_advances_on_project(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        await engine.project(_make_event(position=5))
        await engine.project(_make_event(position=10))
        statuses = await engine.get_status()
        assert statuses[0].global_position == 10
        assert statuses[0].events_processed == 2


class TestEnginePersistence:
    async def test_persists_after_snapshot_interval(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=2)
        proj = StubProjection("snap_test")
        await engine.register(proj)

        await engine.project(_make_event(position=1))
        assert await store.load("snap_test") is None  # not yet

        await engine.project(_make_event(position=2))
        saved = await store.load("snap_test")
        assert saved is not None
        assert saved.global_position == 2

    async def test_stop_flushes_state(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=999)
        proj = StubProjection("flush_test")
        await engine.register(proj)
        await engine.project(_make_event(position=1))
        assert await store.load("flush_test") is None  # interval not reached

        await engine.stop()
        saved = await store.load("flush_test")
        assert saved is not None
        assert saved.global_position == 1


class TestEngineRestore:
    async def test_start_restores_from_store(self) -> None:
        store = InMemoryProjectionStore()
        # Pre-populate store with saved state
        await store.save(
            ProjectionState(
                projection_name="restore_test",
                global_position=50,
                stream_position=None,
                state={"existing": "data"},
                updated_at=datetime.now(UTC),
            )
        )

        engine = InMemoryProjectionEngine(projection_store=store)
        proj = StubProjection("restore_test")
        await engine.register(proj)
        await engine.start()

        # Projection state should be restored
        assert proj.get_state() == {"existing": "data"}
        statuses = await engine.get_status()
        assert statuses[0].global_position == 50


class TestEngineResetClearsStore:
    async def test_reset_all_clears_persisted_state(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=1)
        proj = StubProjection("reset_test")
        await engine.register(proj)
        await engine.project(_make_event(position=1))
        assert await store.load("reset_test") is not None

        await engine.reset_all()
        assert await store.load("reset_test") is None


class TestEngineStatus:
    async def test_get_status_returns_all_projections(self) -> None:
        engine = InMemoryProjectionEngine()
        await engine.register(StubProjection("a"))
        await engine.register(StubProjection("b"))
        statuses = await engine.get_status()
        assert len(statuses) == 2
        names = {s.name for s in statuses}
        assert names == {"a", "b"}

    async def test_status_shows_running_after_start(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        statuses = await engine.get_status()
        assert statuses[0].status == "stopped"

        await engine.start()
        statuses = await engine.get_status()
        assert statuses[0].status == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/infrastructure/tests/projections/test_engine_persistence.py -v`
Expected: FAIL — `get_status` not defined, constructor doesn't accept `projection_store`

- [ ] **Step 3: Write implementation**

Replace the contents of `packages/infrastructure/src/lintel/infrastructure/projections/engine.py`:

```python
"""In-memory projection engine — subscribes to EventBus for reactive projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus, EventStore
    from lintel.domain.projections.protocols import Projection, ProjectionStore

from lintel.contracts.projections import ProjectionState, ProjectionStatus

logger = structlog.get_logger()


@dataclass
class _ProjectionMeta:
    """Internal tracking state per registered projection."""

    projection: Projection
    global_position: int = 0
    events_processed: int = 0
    last_event_at: datetime | None = None


class InMemoryProjectionEngine:
    """Dispatches events to registered projections.

    When an EventBus is provided, the engine subscribes to the bus
    and receives events reactively. The ``project()`` method can still
    be called directly for testing or manual replay.

    When a ProjectionStore is provided, the engine persists projection
    state periodically (every ``snapshot_interval`` events) and restores
    state on ``start()``.
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
        projection_store: ProjectionStore | None = None,
        snapshot_interval: int = 100,
    ) -> None:
        self._metas: list[_ProjectionMeta] = []
        self._event_store = event_store
        self._event_bus = event_bus
        self._projection_store = projection_store
        self._snapshot_interval = snapshot_interval
        self._subscription_id: str | None = None
        self._running = False

    # -- Keep backward compat for code accessing _projections directly ------

    @property
    def _projections(self) -> list[Projection]:
        return [m.projection for m in self._metas]

    async def register(self, projection: Projection) -> None:
        self._metas.append(_ProjectionMeta(projection=projection))
        logger.info(
            "projection_registered",
            name=projection.name,
            event_types=sorted(projection.handled_event_types),
        )

    async def start(self) -> None:
        """Restore state from store, then subscribe to the event bus."""
        # Restore persisted state
        if self._projection_store is not None:
            for meta in self._metas:
                saved = await self._projection_store.load(meta.projection.name)
                if saved is not None:
                    meta.projection.restore_state(saved.state)
                    meta.global_position = saved.global_position
                    logger.info(
                        "projection_state_restored",
                        name=meta.projection.name,
                        position=saved.global_position,
                    )

        # Subscribe to event bus
        if self._event_bus is not None:
            all_types: set[str] = set()
            for meta in self._metas:
                all_types.update(meta.projection.handled_event_types)
            self._subscription_id = await self._event_bus.subscribe(
                frozenset(all_types),
                self,
            )
            logger.info(
                "projection_engine_subscribed",
                event_types_count=len(all_types),
                subscription_id=self._subscription_id,
            )

        self._running = True

    async def stop(self) -> None:
        """Flush state to store and unsubscribe from the event bus."""
        # Flush all projection state before unsubscribing
        if self._projection_store is not None:
            for meta in self._metas:
                await self._persist(meta)

        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

        self._running = False
        logger.info("projection_engine_stopped")

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — called by the EventBus."""
        await self.project(event)

    async def project(self, event: EventEnvelope) -> None:
        for meta in self._metas:
            if event.event_type in meta.projection.handled_event_types:
                await meta.projection.project(event)
                meta.events_processed += 1
                if event.global_position is not None:
                    meta.global_position = event.global_position
                meta.last_event_at = event.occurred_at

                # Periodic persistence
                if (
                    self._projection_store is not None
                    and meta.events_processed % self._snapshot_interval == 0
                ):
                    await self._persist(meta)

    async def _persist(self, meta: _ProjectionMeta) -> None:
        """Save projection state to the store."""
        if self._projection_store is None:
            return
        state = ProjectionState(
            projection_name=meta.projection.name,
            global_position=meta.global_position,
            stream_position=None,
            state=meta.projection.get_state(),
            updated_at=datetime.now(UTC),
        )
        await self._projection_store.save(state)
        logger.debug(
            "projection_state_persisted",
            name=meta.projection.name,
            position=meta.global_position,
        )

    async def reset_all(self) -> None:
        """Reset all projections to empty state and clear persisted state."""
        for meta in self._metas:
            await meta.projection.rebuild([])
            meta.global_position = 0
            meta.events_processed = 0
            meta.last_event_at = None
            if self._projection_store is not None:
                await self._projection_store.delete(meta.projection.name)
        logger.info("projections_reset", count=len(self._metas))

    async def rebuild_all(self, stream_id: str) -> None:
        if not self._event_store:
            msg = "EventStore required for rebuild"
            raise RuntimeError(msg)
        events = await self._event_store.read_stream(stream_id)
        for meta in self._metas:
            matching = [
                e for e in events if e.event_type in meta.projection.handled_event_types
            ]
            await meta.projection.rebuild(matching)
            if matching:
                last = matching[-1]
                if last.global_position is not None:
                    meta.global_position = last.global_position
                meta.events_processed = len(matching)

    async def get_status(self) -> list[ProjectionStatus]:
        """Return runtime status for all registered projections."""
        statuses: list[ProjectionStatus] = []
        for meta in self._metas:
            statuses.append(
                ProjectionStatus(
                    name=meta.projection.name,
                    status="running" if self._running else "stopped",
                    global_position=meta.global_position,
                    lag=0,  # TODO: compute from event store head position
                    last_event_at=meta.last_event_at,
                    events_processed=meta.events_processed,
                )
            )
        return statuses
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/infrastructure/tests/projections/test_engine_persistence.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Run existing engine tests to verify no regressions**

Run: `uv run pytest packages/infrastructure/tests/projections/ -v`
Expected: PASS (all tests including any existing engine tests)

- [ ] **Step 6: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/projections/engine.py packages/infrastructure/tests/projections/test_engine_persistence.py
git commit -m "feat: add position tracking, persistence, and status to ProjectionEngine"
```

---

## Chunk 5: Health Endpoint & Wiring

### Task 7: Add GET /admin/projections endpoint

**Files:**
- Modify: `packages/app/src/lintel/api/routes/admin.py`
- Test: `packages/app/tests/api/test_admin_projections.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/app/tests/api/test_admin_projections.py
"""Tests for GET /admin/projections endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from lintel.contracts.projections import ProjectionStatus


@pytest.fixture
def mock_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.get_status.return_value = [
        ProjectionStatus(
            name="task_backlog",
            status="running",
            global_position=100,
            lag=2,
            last_event_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            events_processed=100,
        ),
        ProjectionStatus(
            name="audit",
            status="running",
            global_position=95,
            lag=7,
            last_event_at=None,
            events_processed=95,
        ),
    ]
    return engine


class TestAdminProjectionsEndpoint:
    async def test_returns_projection_statuses(self, mock_engine: AsyncMock) -> None:
        from lintel.api.app import create_app

        app = create_app()
        app.state.projection_engine = mock_engine

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/admin/projections")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "task_backlog"
        assert data[0]["status"] == "running"
        assert data[0]["global_position"] == 100
        assert data[1]["name"] == "audit"
        assert data[1]["last_event_at"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/app/tests/api/test_admin_projections.py -v`
Expected: FAIL — 404 (endpoint doesn't exist)

- [ ] **Step 3: Write implementation**

Add to `packages/app/src/lintel/api/routes/admin.py` after the `reset_projections` route:

```python
@router.get("/admin/projections")
async def get_projection_status(
    engine: Annotated[InMemoryProjectionEngine, Depends(get_projection_engine)],
) -> list[dict[str, Any]]:
    """Return status of all registered projections."""
    from dataclasses import asdict

    statuses = await engine.get_status()
    result = []
    for s in statuses:
        d = asdict(s)
        # Serialize datetime to ISO string for JSON
        if d["last_event_at"] is not None:
            d["last_event_at"] = d["last_event_at"].isoformat()
        result.append(d)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/app/tests/api/test_admin_projections.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/app/src/lintel/api/routes/admin.py packages/app/tests/api/test_admin_projections.py
git commit -m "feat: add GET /admin/projections health endpoint"
```

### Task 8: Run all affected package tests

- [ ] **Step 1: Run contracts tests**

Run: `make test-contracts`
Expected: PASS

- [ ] **Step 2: Run domain tests**

Run: `make test-domain`
Expected: PASS

- [ ] **Step 3: Run infrastructure tests**

Run: `make test-infrastructure`
Expected: PASS

- [ ] **Step 4: Run app tests**

Run: `make test-app`
Expected: PASS

- [ ] **Step 5: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: PASS

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
# Only if lint/typecheck fixes were applied
git add -u
git commit -m "fix: lint and type errors from projection infrastructure"
```
