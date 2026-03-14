# Automations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Jobs/Automations system that executes workflows on cron schedules, in response to domain events, or on manual trigger, with configurable concurrency policies.

**Architecture:** New `AutomationDefinition` entity in contracts, CRUD routes in app, `AutomationScheduler` background task in domain. Each automation execution reuses `PipelineRun` (linked via `trigger_type="automation:{id}"`). No separate run entity.

**Tech Stack:** Python 3.12+, FastAPI, croniter (new dep), asyncio, existing EventBus

**Spec:** `docs/superpowers/specs/2026-03-14-automations-design.md`

---

## Chunk 1: Domain Types & Events

### Task 1: Add AutomationTriggerType and ConcurrencyPolicy enums

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/types.py:498` (after `WorkflowHook`, before `# --- Artifacts & Test Results ---`)
- Test: `packages/contracts/tests/test_automation_types.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/contracts/tests/test_automation_types.py
"""Tests for automation domain types."""

from lintel.contracts.types import (
    AutomationDefinition,
    AutomationTriggerType,
    ConcurrencyPolicy,
)


class TestAutomationTriggerType:
    def test_cron_value(self) -> None:
        assert AutomationTriggerType.CRON == "cron"

    def test_event_value(self) -> None:
        assert AutomationTriggerType.EVENT == "event"

    def test_manual_value(self) -> None:
        assert AutomationTriggerType.MANUAL == "manual"


class TestConcurrencyPolicy:
    def test_allow_value(self) -> None:
        assert ConcurrencyPolicy.ALLOW == "allow"

    def test_queue_value(self) -> None:
        assert ConcurrencyPolicy.QUEUE == "queue"

    def test_skip_value(self) -> None:
        assert ConcurrencyPolicy.SKIP == "skip"

    def test_cancel_value(self) -> None:
        assert ConcurrencyPolicy.CANCEL == "cancel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py -v`
Expected: FAIL with `ImportError` — types don't exist yet

- [ ] **Step 3: Write the enums**

Add to `packages/contracts/src/lintel/contracts/types.py` after line 498 (after `WorkflowHook`), before `# --- Artifacts & Test Results ---`:

```python
class AutomationTriggerType(StrEnum):
    CRON = "cron"
    EVENT = "event"
    MANUAL = "manual"


class ConcurrencyPolicy(StrEnum):
    ALLOW = "allow"
    QUEUE = "queue"
    SKIP = "skip"
    CANCEL = "cancel"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/lintel/contracts/types.py packages/contracts/tests/test_automation_types.py
git commit -m "feat(contracts): add AutomationTriggerType and ConcurrencyPolicy enums"
```

### Task 2: Add AutomationDefinition dataclass

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/types.py` (after the new enums)
- Test: `packages/contracts/tests/test_automation_types.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/contracts/tests/test_automation_types.py`:

```python
from dataclasses import asdict, FrozenInstanceError
import pytest


class TestAutomationDefinition:
    def test_create_minimal(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Nightly Review",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.CRON,
            trigger_config={"schedule": "0 2 * * *", "timezone": "UTC"},
        )
        assert auto.automation_id == "a-1"
        assert auto.concurrency_policy == ConcurrencyPolicy.QUEUE
        assert auto.enabled is True
        assert auto.max_chain_depth == 3

    def test_frozen(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Test",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.MANUAL,
            trigger_config={},
        )
        with pytest.raises(FrozenInstanceError):
            auto.name = "Changed"  # type: ignore[misc]

    def test_asdict_roundtrip(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Test",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.EVENT,
            trigger_config={"event_types": ["PipelineRunCompleted"]},
            input_parameters={"branch": "main"},
            concurrency_policy=ConcurrencyPolicy.SKIP,
        )
        d = asdict(auto)
        assert d["automation_id"] == "a-1"
        assert d["trigger_config"]["event_types"] == ["PipelineRunCompleted"]
        assert d["concurrency_policy"] == "skip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py::TestAutomationDefinition -v`
Expected: FAIL

- [ ] **Step 3: Write the dataclass**

Add to `packages/contracts/src/lintel/contracts/types.py` after the new enums:

```python
@dataclass(frozen=True)
class AutomationDefinition:
    """Server-side automation rule that executes workflows on schedule or event."""

    automation_id: str
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True
    max_chain_depth: int = 3
    created_at: str = ""
    updated_at: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/lintel/contracts/types.py packages/contracts/tests/test_automation_types.py
git commit -m "feat(contracts): add AutomationDefinition dataclass"
```

### Task 3: Add automation events

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/events.py:410` (after `TriggerFired`, before `# --- Artifact & Test Events ---`)
- Test: `packages/contracts/tests/test_automation_types.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/contracts/tests/test_automation_types.py`:

```python
from lintel.contracts.events import (
    AutomationCreated,
    AutomationUpdated,
    AutomationRemoved,
    AutomationEnabled,
    AutomationDisabled,
    AutomationFired,
    AutomationSkipped,
    AutomationCancelled,
    EVENT_TYPE_MAP,
)


class TestAutomationEvents:
    def test_event_type_values(self) -> None:
        assert AutomationCreated.event_type == "AutomationCreated"
        assert AutomationUpdated.event_type == "AutomationUpdated"
        assert AutomationRemoved.event_type == "AutomationRemoved"
        assert AutomationEnabled.event_type == "AutomationEnabled"
        assert AutomationDisabled.event_type == "AutomationDisabled"
        assert AutomationFired.event_type == "AutomationFired"
        assert AutomationSkipped.event_type == "AutomationSkipped"
        assert AutomationCancelled.event_type == "AutomationCancelled"

    def test_events_in_registry(self) -> None:
        for name in [
            "AutomationCreated",
            "AutomationUpdated",
            "AutomationRemoved",
            "AutomationEnabled",
            "AutomationDisabled",
            "AutomationFired",
            "AutomationSkipped",
            "AutomationCancelled",
        ]:
            assert name in EVENT_TYPE_MAP, f"{name} missing from EVENT_TYPE_MAP"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py::TestAutomationEvents -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the event classes and register them**

Add to `packages/contracts/src/lintel/contracts/events.py` after `TriggerFired` (line 410), before `# --- Artifact & Test Events ---`:

```python
# --- Automation Events ---


@dataclass(frozen=True)
class AutomationCreated(EventEnvelope):
    event_type: str = "AutomationCreated"


@dataclass(frozen=True)
class AutomationUpdated(EventEnvelope):
    event_type: str = "AutomationUpdated"


@dataclass(frozen=True)
class AutomationRemoved(EventEnvelope):
    event_type: str = "AutomationRemoved"


@dataclass(frozen=True)
class AutomationEnabled(EventEnvelope):
    event_type: str = "AutomationEnabled"


@dataclass(frozen=True)
class AutomationDisabled(EventEnvelope):
    event_type: str = "AutomationDisabled"


@dataclass(frozen=True)
class AutomationFired(EventEnvelope):
    event_type: str = "AutomationFired"


@dataclass(frozen=True)
class AutomationSkipped(EventEnvelope):
    event_type: str = "AutomationSkipped"


@dataclass(frozen=True)
class AutomationCancelled(EventEnvelope):
    event_type: str = "AutomationCancelled"
```

Add all 8 to `EVENT_TYPE_MAP` after `TriggerFired` entry (line 1140):

```python
        AutomationCreated,
        AutomationUpdated,
        AutomationRemoved,
        AutomationEnabled,
        AutomationDisabled,
        AutomationFired,
        AutomationSkipped,
        AutomationCancelled,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_automation_types.py -v`
Expected: All PASS

- [ ] **Step 5: Run contracts package tests**

Run: `make test-contracts`
Expected: All PASS — no regressions

- [ ] **Step 6: Commit**

```bash
git add packages/contracts/src/lintel/contracts/events.py packages/contracts/tests/test_automation_types.py
git commit -m "feat(contracts): add automation events and register in EVENT_TYPE_MAP"
```

---

## Chunk 2: CRUD Routes & Store

### Task 4: Create automation CRUD routes with InMemoryStore

**Files:**
- Create: `packages/app/src/lintel/api/routes/automations.py`
- Create: `packages/app/src/lintel/api/schemas/automations.py`
- Test: `packages/app/tests/api/test_automations.py`

**Pattern:** Follow `packages/app/src/lintel/api/routes/triggers.py` exactly.

- [ ] **Step 1: Write the failing tests**

```python
# packages/app/tests/api/test_automations.py
"""Tests for automations API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _automation_body(
    automation_id: str = "a-1",
    name: str = "Nightly Review",
    trigger_type: str = "cron",
) -> dict:
    return {
        "automation_id": automation_id,
        "project_id": "proj-1",
        "workflow_definition_id": "wf-1",
        "name": name,
        "trigger_type": trigger_type,
        "trigger_config": {"schedule": "0 2 * * *", "timezone": "UTC"},
    }


class TestAutomationsAPI:
    def test_create_automation_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/automations", json=_automation_body())
        assert resp.status_code == 201
        data = resp.json()
        assert data["automation_id"] == "a-1"
        assert data["name"] == "Nightly Review"
        assert data["enabled"] is True
        assert data["concurrency_policy"] == "queue"
        assert data["max_chain_depth"] == 3
        assert data["created_at"] != ""

    def test_list_automations_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/automations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_automation_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-2"))
        resp = client.get("/api/v1/automations/a-2")
        assert resp.status_code == 200
        assert resp.json()["automation_id"] == "a-2"

    def test_get_automation_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/automations/nonexistent")
        assert resp.status_code == 404

    def test_update_automation(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-3"))
        resp = client.patch(
            "/api/v1/automations/a-3",
            json={"name": "Updated", "concurrency_policy": "skip"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["concurrency_policy"] == "skip"

    def test_delete_automation_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-4"))
        resp = client.delete("/api/v1/automations/a-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/automations/a-4").status_code == 404

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = _automation_body("a-dup")
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations", json=body)
        assert resp.status_code == 409

    def test_list_filter_by_project(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-5"))
        resp = client.get("/api/v1/automations?project_id=proj-1")
        assert len(resp.json()) == 1
        resp2 = client.get("/api/v1/automations?project_id=other")
        assert len(resp2.json()) == 0

    def test_manual_trigger_returns_200(self, client: TestClient) -> None:
        body = _automation_body("a-6", trigger_type="manual")
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations/a-6/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_run_id" in data

    def test_trigger_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/automations/nonexistent/trigger")
        assert resp.status_code == 404

    def test_trigger_disabled_returns_409(self, client: TestClient) -> None:
        body = _automation_body("a-7", trigger_type="manual")
        body["enabled"] = False
        client.post("/api/v1/automations", json=body)
        resp = client.post("/api/v1/automations/a-7/trigger")
        assert resp.status_code == 409

    def test_list_runs_empty(self, client: TestClient) -> None:
        client.post("/api/v1/automations", json=_automation_body("a-8"))
        resp = client.get("/api/v1/automations/a-8/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_after_trigger(self, client: TestClient) -> None:
        body = _automation_body("a-9", trigger_type="manual")
        client.post("/api/v1/automations", json=body)
        client.post("/api/v1/automations/a-9/trigger")
        resp = client.get("/api/v1/automations/a-9/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/app/tests/api/test_automations.py -v`
Expected: FAIL with `ImportError` or route not found

- [ ] **Step 3: Create the schemas file**

```python
# packages/app/src/lintel/api/schemas/automations.py
"""Pydantic schemas for automation endpoints."""

from uuid import uuid4

from croniter import croniter
from pydantic import BaseModel, Field, model_validator

from lintel.contracts.types import AutomationTriggerType, ConcurrencyPolicy


def _validate_trigger_config(
    trigger_type: AutomationTriggerType,
    trigger_config: dict[str, object],
    instance: object,
) -> object:
    """Validate trigger_config shape matches trigger_type."""
    if trigger_type == AutomationTriggerType.CRON:
        schedule = trigger_config.get("schedule")
        if not schedule or not isinstance(schedule, str):
            msg = "Cron trigger requires 'schedule' string in trigger_config"
            raise ValueError(msg)
        if not croniter.is_valid(str(schedule)):
            msg = f"Invalid cron expression: {schedule}"
            raise ValueError(msg)
    elif trigger_type == AutomationTriggerType.EVENT:
        event_types = trigger_config.get("event_types")
        if not event_types or not isinstance(event_types, list) or len(event_types) == 0:
            msg = "Event trigger requires non-empty 'event_types' list in trigger_config"
            raise ValueError(msg)
    return instance


class CreateAutomationRequest(BaseModel):
    automation_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = Field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True

    @model_validator(mode="after")
    def validate_trigger_config(self) -> "CreateAutomationRequest":
        return _validate_trigger_config(self.trigger_type, self.trigger_config, self)


class UpdateAutomationRequest(BaseModel):
    name: str | None = None
    trigger_config: dict[str, object] | None = None
    input_parameters: dict[str, object] | None = None
    concurrency_policy: ConcurrencyPolicy | None = None
    enabled: bool | None = None
    max_chain_depth: int | None = None
```

- [ ] **Step 4: Create the routes file with InMemoryAutomationStore**

```python
# packages/app/src/lintel/api/routes/automations.py
"""Automation CRUD endpoints."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request

from lintel.api.container import AppContainer
from lintel.api.schemas.automations import CreateAutomationRequest, UpdateAutomationRequest
from lintel.contracts.events import (
    AutomationCreated,
    AutomationDisabled,
    AutomationEnabled,
    AutomationFired,
    AutomationRemoved,
    AutomationUpdated,
)
from lintel.contracts.types import AutomationDefinition, PipelineRun, Stage
from lintel.domain.event_dispatcher import dispatch_event

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class InMemoryAutomationStore:
    """Simple in-memory store for automations."""

    def __init__(self) -> None:
        self._automations: dict[str, AutomationDefinition] = {}

    async def add(self, automation: AutomationDefinition) -> None:
        self._automations[automation.automation_id] = automation

    async def get(self, automation_id: str) -> AutomationDefinition | None:
        return self._automations.get(automation_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[AutomationDefinition]:
        items = list(self._automations.values())
        if project_id is not None:
            items = [a for a in items if a.project_id == project_id]
        return items

    async def update(self, automation: AutomationDefinition) -> None:
        if automation.automation_id not in self._automations:
            msg = f"Automation {automation.automation_id} not found"
            raise KeyError(msg)
        self._automations[automation.automation_id] = automation

    async def remove(self, automation_id: str) -> None:
        if automation_id not in self._automations:
            msg = f"Automation {automation_id} not found"
            raise KeyError(msg)
        del self._automations[automation_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/automations", status_code=201)
@inject
async def create_automation(
    body: CreateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.automation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Automation already exists")
    now = datetime.now(timezone.utc).isoformat()
    automation = AutomationDefinition(
        automation_id=body.automation_id,
        name=body.name,
        project_id=body.project_id,
        workflow_definition_id=body.workflow_definition_id,
        trigger_type=body.trigger_type,
        trigger_config=body.trigger_config,
        input_parameters=body.input_parameters,
        concurrency_policy=body.concurrency_policy,
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )
    await store.add(automation)
    await dispatch_event(
        request,
        AutomationCreated(payload={"resource_id": automation.automation_id}),
        stream_id=f"automation:{automation.automation_id}",
    )
    return asdict(automation)


@router.get("/automations")
@inject
async def list_automations(
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    automations = await store.list_all(project_id=project_id)
    return [asdict(a) for a in automations]


@router.get("/automations/{automation_id}")
@inject
async def get_automation(
    automation_id: str,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return asdict(automation)


@router.patch("/automations/{automation_id}")
@inject
async def update_automation(
    automation_id: str,
    body: UpdateAutomationRequest,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    updates = body.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated = AutomationDefinition(**{**asdict(automation), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        AutomationUpdated(payload={"resource_id": automation_id}),
        stream_id=f"automation:{automation_id}",
    )
    # Emit enabled/disabled events when toggled
    if "enabled" in updates and updates["enabled"] != automation.enabled:
        evt_cls = AutomationEnabled if updates["enabled"] else AutomationDisabled
        await dispatch_event(
            request,
            evt_cls(payload={"resource_id": automation_id}),
            stream_id=f"automation:{automation_id}",
        )
    return asdict(updated)


@router.delete("/automations/{automation_id}", status_code=204)
@inject
async def delete_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
) -> None:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    await store.remove(automation_id)
    await dispatch_event(
        request,
        AutomationRemoved(payload={"resource_id": automation_id}),
        stream_id=f"automation:{automation_id}",
    )


@router.post("/automations/{automation_id}/trigger")
@inject
async def trigger_automation(
    automation_id: str,
    request: Request,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    pipeline_store: Any = Depends(Provide[AppContainer.pipeline_store]),  # noqa: B008
) -> dict[str, Any]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    if not automation.enabled:
        raise HTTPException(status_code=409, detail="Automation is disabled")

    # Create a pipeline run for this automation execution
    run_id = str(uuid4())
    pipeline_run = PipelineRun(
        run_id=run_id,
        project_id=automation.project_id,
        trigger_type=f"automation:{automation_id}",
    )
    await pipeline_store.add(pipeline_run)
    await dispatch_event(
        request,
        AutomationFired(
            payload={
                "resource_id": automation_id,
                "pipeline_run_id": run_id,
                "trigger_type": "manual",
            },
        ),
        stream_id=f"automation:{automation_id}",
    )
    return {"automation_id": automation_id, "pipeline_run_id": run_id}


@router.get("/automations/{automation_id}/runs")
@inject
async def list_automation_runs(
    automation_id: str,
    store: InMemoryAutomationStore = Depends(Provide[AppContainer.automation_store]),  # noqa: B008
    pipeline_store: Any = Depends(Provide[AppContainer.pipeline_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    automation = await store.get(automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    all_runs = await pipeline_store.list_all()
    prefix = f"automation:{automation_id}"
    matching = [r for r in all_runs if _get_trigger_type(r) == prefix]
    return [asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in matching]


def _get_trigger_type(run: Any) -> str:  # noqa: ANN401
    """Extract trigger_type from either a dataclass or dict."""
    if isinstance(run, dict):
        return run.get("trigger_type", "")
    return getattr(run, "trigger_type", "")
```

- [ ] **Step 5: Register the store and route in app.py**

In `packages/app/src/lintel/api/container.py`, add after `board_store` (line 76):

```python
    automation_store: providers.Provider[Any] = providers.Object(None)
```

In `packages/app/src/lintel/api/app.py`:

1. Add import of `InMemoryAutomationStore` from `lintel.api.routes.automations` (in the in-memory store imports section)
2. Add `"automation_store": InMemoryAutomationStore(),` to `_create_in_memory_stores()` after `trigger_store` (line 153)
3. Add `app.include_router(automations.router, prefix="/api/v1", tags=["automations"])` to route registration (after triggers, line 604)
4. Add `from lintel.api.routes import automations` to the route imports section

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest packages/app/tests/api/test_automations.py -v`
Expected: All PASS

- [ ] **Step 7: Run app package tests for regressions**

Run: `make test-app`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add packages/app/src/lintel/api/routes/automations.py packages/app/src/lintel/api/schemas/automations.py packages/app/src/lintel/api/container.py packages/app/src/lintel/api/app.py packages/app/tests/api/test_automations.py
git commit -m "feat(app): add automation CRUD routes with InMemoryStore"
```

---

## Chunk 3: Postgres Store & croniter Dependency

### Task 5: Add PostgresAutomationStore

**Files:**
- Modify: `packages/infrastructure/src/lintel/infrastructure/persistence/stores.py:201` (after `PostgresTriggerStore`)
- Modify: `packages/app/src/lintel/api/app.py` (Postgres store wiring)

- [ ] **Step 1: Add the Postgres store class**

Add to `packages/infrastructure/src/lintel/infrastructure/persistence/stores.py` after `PostgresTriggerStore` (line 201):

```python
class PostgresAutomationStore(PostgresCrudStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        from lintel.contracts.types import AutomationDefinition

        super().__init__(pool, "automation", "automation_id", AutomationDefinition)
```

- [ ] **Step 2: Wire into app.py Postgres stores**

In `packages/app/src/lintel/api/app.py`:

1. Add `PostgresAutomationStore` to the import from `lintel.infrastructure.persistence.stores` (line 204-228)
2. Add `"automation_store": PostgresAutomationStore(pool),` to `_create_postgres_stores()` return dict (after `trigger_store`, line 331)

- [ ] **Step 3: Run app tests**

Run: `make test-app`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add packages/infrastructure/src/lintel/infrastructure/persistence/stores.py packages/app/src/lintel/api/app.py
git commit -m "feat(infrastructure): add PostgresAutomationStore"
```

### Task 6: Add croniter dependency

**Files:**
- Modify: `packages/domain/pyproject.toml`

- [ ] **Step 1: Add croniter to domain package dependencies**

Run: `cd packages/domain && uv add croniter`

- [ ] **Step 2: Verify install**

Run: `uv run python -c "import croniter; print(croniter.__version__)"`
Expected: Prints version number

- [ ] **Step 3: Commit**

```bash
git add packages/domain/pyproject.toml uv.lock
git commit -m "feat(domain): add croniter dependency for cron scheduling"
```

---

## Chunk 4: AutomationScheduler

### Task 7: Build the AutomationScheduler with cron evaluation

**Files:**
- Create: `packages/domain/src/lintel/domain/automation_scheduler.py`
- Test: `packages/domain/tests/domain/test_automation_scheduler.py`

- [ ] **Step 1: Write failing tests for cron evaluation**

```python
# packages/domain/tests/domain/test_automation_scheduler.py
"""Tests for AutomationScheduler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from lintel.contracts.types import (
    AutomationDefinition,
    AutomationTriggerType,
    ConcurrencyPolicy,
)
from lintel.domain.automation_scheduler import AutomationScheduler


def _cron_automation(
    automation_id: str = "a-1",
    schedule: str = "* * * * *",
    enabled: bool = True,
    concurrency: ConcurrencyPolicy = ConcurrencyPolicy.ALLOW,
) -> AutomationDefinition:
    return AutomationDefinition(
        automation_id=automation_id,
        name="Test",
        project_id="proj-1",
        workflow_definition_id="wf-1",
        trigger_type=AutomationTriggerType.CRON,
        trigger_config={"schedule": schedule, "timezone": "UTC"},
        concurrency_policy=concurrency,
        enabled=enabled,
    )


class TestCronEvaluation:
    async def test_fires_when_due(self) -> None:
        store = AsyncMock()
        store.list_all.return_value = [_cron_automation()]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        await scheduler.tick_cron()
        fire_fn.assert_called_once()

    async def test_skips_disabled(self) -> None:
        store = AsyncMock()
        store.list_all.return_value = [_cron_automation(enabled=False)]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        await scheduler.tick_cron()
        fire_fn.assert_not_called()

    async def test_no_double_fire(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(schedule="0 2 * * *")
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        # Mark as recently fired
        scheduler._last_fired["a-1"] = datetime.now(timezone.utc)
        await scheduler.tick_cron()
        fire_fn.assert_not_called()


class TestConcurrencyPolicies:
    async def test_skip_policy_skips_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.SKIP)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        skip_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store, fire_fn=fire_fn, skip_fn=skip_fn,
        )
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_not_called()
        skip_fn.assert_called_once()

    async def test_allow_policy_fires_even_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.ALLOW)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_called_once()

    async def test_queue_policy_enqueues_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.QUEUE)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_not_called()
        assert len(scheduler._queues["a-1"]) == 1

    async def test_cancel_policy_cancels_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.CANCEL)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        cancel_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store, fire_fn=fire_fn, cancel_fn=cancel_fn,
        )
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        cancel_fn.assert_called_once_with("a-1", "run-123")
        fire_fn.assert_called_once()

    async def test_queue_dequeues_on_completion(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.QUEUE)
        store.get.return_value = auto
        fire_fn = AsyncMock(return_value="run-next")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        scheduler._queues["a-1"].append({"trigger": "cron"})
        await scheduler.mark_run_completed("a-1", "run-123")
        fire_fn.assert_called_once()
        assert scheduler._active_runs["a-1"] == "run-next"
        assert len(scheduler._queues["a-1"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/domain/tests/domain/test_automation_scheduler.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement AutomationScheduler**

```python
# packages/domain/src/lintel/domain/automation_scheduler.py
"""Background automation scheduler with cron evaluation and concurrency control."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from croniter import croniter

from lintel.contracts.types import AutomationTriggerType, ConcurrencyPolicy

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


class AutomationScheduler:
    """Evaluates cron schedules and enforces concurrency policies."""

    TICK_INTERVAL_SECONDS = 60

    def __init__(
        self,
        automation_store: Any,
        fire_fn: Callable[..., Coroutine[Any, Any, str]],
        skip_fn: Callable[..., Coroutine[Any, Any, None]] | None = None,
        cancel_fn: Callable[..., Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._store = automation_store
        self._fire_fn = fire_fn
        self._skip_fn = skip_fn or _noop_skip
        self._cancel_fn = cancel_fn or _noop_cancel
        self._last_fired: dict[str, datetime] = {}
        self._active_runs: dict[str, str] = {}  # automation_id -> run_id
        self._queues: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def tick_cron(self) -> list[str]:
        """Evaluate all cron automations. Returns list of fired automation IDs."""
        all_automations = await self._store.list_all()
        now = datetime.now(timezone.utc)
        fired: list[str] = []

        for auto in all_automations:
            if not auto.enabled:
                continue
            if auto.trigger_type != AutomationTriggerType.CRON:
                continue

            schedule = auto.trigger_config.get("schedule")
            if not schedule:
                continue

            tz = auto.trigger_config.get("timezone", "UTC")
            if not self._is_due(auto.automation_id, str(schedule), now):
                continue

            result = await self._apply_concurrency(auto, {"trigger": "cron"})
            if result:
                fired.append(auto.automation_id)

        return fired

    def _is_due(self, automation_id: str, schedule: str, now: datetime) -> bool:
        """Check if a cron automation is due to fire."""
        last = self._last_fired.get(automation_id)
        cron = croniter(schedule, now)
        prev = cron.get_prev(datetime).replace(tzinfo=timezone.utc)

        if last is not None and last >= prev:
            return False
        return True

    async def _apply_concurrency(
        self,
        auto: Any,
        trigger_metadata: dict[str, Any],
    ) -> bool:
        """Apply concurrency policy. Returns True if fired."""
        aid = auto.automation_id
        active = self._active_runs.get(aid)

        if auto.concurrency_policy == ConcurrencyPolicy.ALLOW:
            run_id = await self._fire_fn(auto, trigger_metadata)
            self._last_fired[aid] = datetime.now(timezone.utc)
            return True

        if active is None:
            run_id = await self._fire_fn(auto, trigger_metadata)
            self._active_runs[aid] = run_id
            self._last_fired[aid] = datetime.now(timezone.utc)
            return True

        if auto.concurrency_policy == ConcurrencyPolicy.SKIP:
            await self._skip_fn(auto, "concurrency:skip")
            return False

        if auto.concurrency_policy == ConcurrencyPolicy.QUEUE:
            self._queues[aid].append(trigger_metadata)
            return False

        if auto.concurrency_policy == ConcurrencyPolicy.CANCEL:
            await self._cancel_fn(aid, active)
            run_id = await self._fire_fn(auto, trigger_metadata)
            self._active_runs[aid] = run_id
            self._last_fired[aid] = datetime.now(timezone.utc)
            return True

        return False

    async def mark_run_completed(self, automation_id: str, run_id: str) -> None:
        """Called when a pipeline run completes — dequeue next if queued."""
        if self._active_runs.get(automation_id) == run_id:
            del self._active_runs[automation_id]

        queue = self._queues.get(automation_id, [])
        if queue:
            metadata = queue.pop(0)
            auto = await self._store.get(automation_id)
            if auto and auto.enabled:
                new_run_id = await self._fire_fn(auto, metadata)
                self._active_runs[automation_id] = new_run_id

    async def run(self) -> None:
        """Run the cron scheduler loop indefinitely."""
        while True:
            await self.tick_cron()
            await asyncio.sleep(self.TICK_INTERVAL_SECONDS)


async def _noop_skip(auto: Any, reason: str) -> None:  # noqa: ANN401
    pass


async def _noop_cancel(automation_id: str, run_id: str) -> None:
    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/domain/tests/domain/test_automation_scheduler.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/domain/src/lintel/domain/automation_scheduler.py packages/domain/tests/domain/test_automation_scheduler.py
git commit -m "feat(domain): add AutomationScheduler with cron and concurrency"
```

### Task 8: Add event-triggered automation support

**Files:**
- Modify: `packages/domain/src/lintel/domain/automation_scheduler.py`
- Test: `packages/domain/tests/domain/test_automation_scheduler.py`

- [ ] **Step 1: Write failing tests for event triggers**

Append to `packages/domain/tests/domain/test_automation_scheduler.py`:

```python
from lintel.contracts.events import EventEnvelope


def _event_automation(
    automation_id: str = "a-evt",
    event_types: list[str] | None = None,
    max_chain_depth: int = 3,
) -> AutomationDefinition:
    return AutomationDefinition(
        automation_id=automation_id,
        name="On Complete",
        project_id="proj-1",
        workflow_definition_id="wf-1",
        trigger_type=AutomationTriggerType.EVENT,
        trigger_config={"event_types": event_types or ["PipelineRunCompleted"]},
        max_chain_depth=max_chain_depth,
    )


class TestEventTriggers:
    async def test_fires_on_matching_event(self) -> None:
        store = AsyncMock()
        auto = _event_automation()
        store.list_all.return_value = [auto]
        store.get.return_value = auto
        fire_fn = AsyncMock(return_value="run-1")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)

        event = EventEnvelope(
            event_type="PipelineRunCompleted",
            payload={"resource_id": "some-run"},
        )
        await scheduler.handle_event(event)
        fire_fn.assert_called_once()

    async def test_ignores_non_matching_event(self) -> None:
        store = AsyncMock()
        auto = _event_automation()
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)

        event = EventEnvelope(
            event_type="WorkItemCreated",
            payload={"resource_id": "wi-1"},
        )
        await scheduler.handle_event(event)
        fire_fn.assert_not_called()

    async def test_chain_depth_exceeded_skips(self) -> None:
        store = AsyncMock()
        auto = _event_automation(max_chain_depth=2)
        store.list_all.return_value = [auto]
        store.get.return_value = auto
        fire_fn = AsyncMock()
        skip_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store, fire_fn=fire_fn, skip_fn=skip_fn,
        )
        # Simulate chain depth exceeding limit
        scheduler._chain_depths["corr-1"] = 3
        event = EventEnvelope(
            event_type="PipelineRunCompleted",
            payload={"resource_id": "r-1"},
            correlation_id="corr-1",
        )
        await scheduler.handle_event(event)
        fire_fn.assert_not_called()
        skip_fn.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/domain/tests/domain/test_automation_scheduler.py::TestEventTriggers -v`
Expected: FAIL — `handle_event` method doesn't exist

- [ ] **Step 3: Add handle_event method to AutomationScheduler**

Add to `AutomationScheduler.__init__`:
```python
        self._chain_depths: dict[str, int] = {}  # correlation_id -> depth
```

Add method to `AutomationScheduler`:
```python
    async def handle_event(self, event: Any) -> None:
        """Handle an incoming domain event, firing matching automations."""
        all_automations = await self._store.list_all()
        for auto in all_automations:
            if not auto.enabled:
                continue
            if auto.trigger_type != AutomationTriggerType.EVENT:
                continue
            event_types = auto.trigger_config.get("event_types", [])
            if event.event_type not in event_types:
                continue

            # Chain depth guard
            corr_id = getattr(event, "correlation_id", "")
            if corr_id:
                depth = self._chain_depths.get(corr_id, 0)
                if depth >= auto.max_chain_depth:
                    await self._skip_fn(auto, "max_chain_depth_exceeded")
                    continue

            metadata = {"trigger": "event", "event_type": event.event_type}
            result = await self._apply_concurrency(auto, metadata)
            if result and corr_id:
                self._chain_depths[corr_id] = self._chain_depths.get(corr_id, 0) + 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/domain/tests/domain/test_automation_scheduler.py -v`
Expected: All PASS

- [ ] **Step 5: Run domain package tests**

Run: `make test-domain`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add packages/domain/src/lintel/domain/automation_scheduler.py packages/domain/tests/domain/test_automation_scheduler.py
git commit -m "feat(domain): add event-triggered automation support with chain depth guard"
```

---

## Chunk 5: App Lifespan Wiring & Lint

### Task 9: Wire AutomationScheduler into app lifespan

**Files:**
- Modify: `packages/app/src/lintel/api/app.py`

This task does NOT need TDD — it's integration wiring. The tests from Task 4 already cover the routes; the scheduler is tested in Task 7/8.

- [ ] **Step 1: Find the lifespan function in app.py**

Look for the `async def lifespan(app: FastAPI)` function. It initializes stores, services, and background tasks.

- [ ] **Step 2: Add AutomationScheduler initialization**

After the stores and services are created but before the yield, add:

```python
    # Start automation scheduler
    from lintel.domain.automation_scheduler import AutomationScheduler

    async def _fire_automation(auto, metadata):
        """Create a PipelineRun and emit AutomationFired event."""
        from uuid import uuid4
        from lintel.contracts.types import PipelineRun
        from lintel.contracts.events import AutomationFired
        run_id = str(uuid4())
        pipeline_run = PipelineRun(
            run_id=run_id,
            project_id=auto.project_id,
            trigger_type=f"automation:{auto.automation_id}",
        )
        await stores["pipeline_store"].add(pipeline_run)
        # Emit AutomationFired event
        event = AutomationFired(
            payload={
                "resource_id": auto.automation_id,
                "pipeline_run_id": run_id,
                "trigger_type": metadata.get("trigger", "unknown"),
            },
        )
        await services["event_bus"].publish(event)
        return run_id

    automation_scheduler = AutomationScheduler(
        automation_store=stores["automation_store"],
        fire_fn=_fire_automation,
    )

    # Recover last_fired_at from event store to prevent double-firing after restart
    from lintel.contracts.events import AutomationFired
    all_automations = await stores["automation_store"].list_all()
    for auto in all_automations:
        events = await stores["event_store"].get_events(
            stream_id=f"automation:{auto.automation_id}",
        )
        fired_events = [e for e in events if e.event_type == "AutomationFired"]
        if fired_events:
            last = fired_events[-1]
            ts = getattr(last, "timestamp", "")
            if ts:
                from datetime import datetime, timezone
                automation_scheduler._last_fired[auto.automation_id] = (
                    datetime.fromisoformat(ts)
                )

    # Subscribe event-triggered automations to EventBus
    async def _on_event(event):
        await automation_scheduler.handle_event(event)

    event_types = set()
    for auto in all_automations:
        if auto.trigger_type == "event" and auto.enabled:
            for et in auto.trigger_config.get("event_types", []):
                event_types.add(et)
    if event_types:
        await services["event_bus"].subscribe(
            frozenset(event_types), type("_H", (), {"handle": staticmethod(_on_event)})()
        )

    # Subscribe to pipeline completion for queue dequeue
    async def _on_pipeline_complete(event):
        run_id = event.payload.get("resource_id", "")
        trigger = event.payload.get("trigger_type", "")
        if trigger.startswith("automation:"):
            aid = trigger.split(":", 1)[1]
            await automation_scheduler.mark_run_completed(aid, run_id)

    await services["event_bus"].subscribe(
        frozenset({"PipelineRunCompleted", "PipelineRunFailed"}),
        type("_PCH", (), {"handle": staticmethod(_on_pipeline_complete)})(),
    )

    scheduler_task = asyncio.create_task(automation_scheduler.run())
    app.state._background_tasks.add(scheduler_task)
    scheduler_task.add_done_callback(app.state._background_tasks.discard)
```

- [ ] **Step 3: Run app tests**

Run: `make test-app`
Expected: All PASS

- [ ] **Step 4: Run lint**

Run: `make lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/app/src/lintel/api/app.py
git commit -m "feat(app): wire AutomationScheduler into app lifespan"
```

### Task 10: Final validation

- [ ] **Step 1: Run all affected package tests**

Run: `make test-contracts && make test-domain && make test-app`
Expected: All PASS

- [ ] **Step 2: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: PASS (fix any issues)

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve lint/type issues from automations feature"
```

**Note on MCP tools:** The app uses `FastApiMCP` (app.py line 624-631) which auto-exposes all registered API routes as MCP tools. No separate MCP implementation is needed — the automation routes will automatically be available as `automations_create_automation`, `automations_list_automations`, etc.
