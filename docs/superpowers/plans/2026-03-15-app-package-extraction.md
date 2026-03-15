# App Package Extraction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract every CRUD entity from `packages/app/` into its own package with isolated stores, routes, and tests.

**Architecture:** Each CRUD entity becomes a standalone uv workspace package under `packages/`. A new `lintel-api-support` package provides shared utilities (`StoreProvider`, `dispatch_event`). The `app` package becomes a thin composition root that imports routers and wires stores.

**Tech Stack:** Python 3.12+, FastAPI, uv workspace, hatchling build

**Worktree:** All work happens in `/Users/bamdad/projects/lintel-extraction` (branch `feat/app-package-extraction`)

---

## Chunk 1: Foundation — `lintel-api-support` Package

### Task 1: Create `lintel-api-support` package scaffold

**Files:**
- Create: `packages/api-support/pyproject.toml`
- Create: `packages/api-support/src/lintel/api_support/__init__.py`
- Create: `packages/api-support/src/lintel/api_support/py.typed`
- Create: `packages/api-support/src/lintel/api_support/provider.py`
- Create: `packages/api-support/src/lintel/api_support/event_dispatcher.py`

- [ ] **Step 1: Write failing test for StoreProvider**

Create: `packages/api-support/tests/test_provider.py`

```python
"""Tests for StoreProvider."""

import pytest

from lintel.api_support.provider import StoreProvider


class TestStoreProvider:
    def test_raises_when_not_configured(self) -> None:
        provider = StoreProvider()
        with pytest.raises(RuntimeError, match="Store not configured"):
            provider()

    def test_returns_instance_after_override(self) -> None:
        provider = StoreProvider()
        sentinel = object()
        provider.override(sentinel)
        assert provider() is sentinel

    def test_override_replaces_previous(self) -> None:
        provider = StoreProvider()
        first = object()
        second = object()
        provider.override(first)
        provider.override(second)
        assert provider() is second

    def test_override_with_none_resets(self) -> None:
        provider = StoreProvider()
        provider.override(object())
        provider.override(None)
        with pytest.raises(RuntimeError):
            provider()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/bamdad/projects/lintel-extraction && uv run pytest packages/api-support/tests/test_provider.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create pyproject.toml**

Create: `packages/api-support/pyproject.toml`

```toml
[project]
name = "lintel-api-support"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "lintel-contracts",
    "fastapi>=0.115",
    "structlog>=24.4",
]

[tool.uv.sources]
lintel-contracts = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
only-include = ["src/lintel/api_support"]

[tool.hatch.build.targets.wheel.sources]
"src" = ""
```

- [ ] **Step 4: Create StoreProvider**

Create: `packages/api-support/src/lintel/api_support/provider.py`

```python
"""Minimal store provider for dependency injection without dependency-injector."""

from __future__ import annotations

from typing import Any


class StoreProvider:
    """Store holder that can be overridden at app startup.

    Use as a FastAPI ``Depends()`` callable::

        user_store_provider = StoreProvider()

        @router.get("/users")
        async def list_users(
            store = Depends(user_store_provider),
        ):
            ...

    Wire at startup::

        user_store_provider.override(InMemoryUserStore())
    """

    def __init__(self) -> None:
        self._instance: Any = None

    def override(self, instance: Any) -> None:  # noqa: ANN401
        """Set or replace the store instance."""
        self._instance = instance

    def __call__(self) -> Any:  # noqa: ANN401
        """Return the store instance (called by FastAPI Depends)."""
        if self._instance is None:
            raise RuntimeError("Store not configured — call .override() at app startup")
        return self._instance
```

Create: `packages/api-support/src/lintel/api_support/__init__.py`

```python
"""Shared API support utilities for extracted route packages."""
```

Create: `packages/api-support/src/lintel/api_support/py.typed` (empty marker file)

- [ ] **Step 5: Create event_dispatcher (move from app)**

Create: `packages/api-support/src/lintel/api_support/event_dispatcher.py`

Copy the contents of `packages/app/src/lintel/api/domain/event_dispatcher.py` exactly as-is. The imports and logic stay the same — it reads from `request.app.state.event_store`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/bamdad/projects/lintel-extraction && uv sync --all-packages && uv run pytest packages/api-support/tests/test_provider.py -v`
Expected: 4 PASSED

- [ ] **Step 7: Add to workspace config**

Modify: `pyproject.toml` (root) — add `packages/api-support/tests` to `testpaths` list and `packages/api-support/src` to `mypy_path`.

- [ ] **Step 8: Commit**

```bash
cd /Users/bamdad/projects/lintel-extraction
git add packages/api-support/ pyproject.toml
git commit -m "feat: add lintel-api-support package with StoreProvider and event_dispatcher"
```

---

### Task 2: Extract `lintel-users` as proof-of-concept

**Files:**
- Create: `packages/users/pyproject.toml`
- Create: `packages/users/src/lintel/users/py.typed`
- Create: `packages/users/src/lintel/users/__init__.py`
- Create: `packages/users/src/lintel/users/store.py`
- Create: `packages/users/src/lintel/users/routes.py`
- Create: `packages/users/tests/conftest.py`
- Create: `packages/users/tests/test_routes.py`
- Modify: `packages/app/src/lintel/api/app.py` — update imports
- Modify: `packages/app/src/lintel/api/container.py` — keep user_store provider
- Delete: `packages/app/src/lintel/api/routes/users.py` — after migration
- Delete: `packages/app/tests/api/test_users.py` — after migration

- [ ] **Step 1: Write test for isolated users package**

Create: `packages/users/tests/conftest.py`

```python
"""Test fixtures for users package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.users.routes import router, user_store_provider
from lintel.users.store import InMemoryUserStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryUserStore()
    user_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    user_store_provider.override(None)
```

Create: `packages/users/tests/test_routes.py`

```python
"""Tests for users API routes."""

from fastapi.testclient import TestClient


class TestUsersAPI:
    def test_create_user_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"user_id": "u-1", "name": "Alice", "email": "alice@example.com"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "u-1"
        assert data["name"] == "Alice"
        assert data["role"] == "member"

    def test_list_users_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_user_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/users", json={"user_id": "u-2", "name": "Bob"})
        resp = client.get("/api/v1/users/u-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"

    def test_get_user_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_delete_user_returns_204(self, client: TestClient) -> None:
        client.post("/api/v1/users", json={"user_id": "u-3", "name": "Charlie"})
        resp = client.delete("/api/v1/users/u-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/users/u-3").status_code == 404

    def test_update_user(self, client: TestClient) -> None:
        client.post("/api/v1/users", json={"user_id": "u-4", "name": "Dan"})
        resp = client.patch("/api/v1/users/u-4", json={"name": "Daniel"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Daniel"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/users", json={"user_id": "u-5", "name": "Eve"})
        resp = client.post("/api/v1/users", json={"user_id": "u-5", "name": "Eve2"})
        assert resp.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/bamdad/projects/lintel-extraction && uv run pytest packages/users/tests/ -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create pyproject.toml**

Create: `packages/users/pyproject.toml`

```toml
[project]
name = "lintel-users"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "lintel-contracts",
    "lintel-domain",
    "lintel-api-support",
    "fastapi>=0.115",
    "pydantic>=2.10",
    "structlog>=24.4",
]

[tool.uv.sources]
lintel-contracts = { workspace = true }
lintel-domain = { workspace = true }
lintel-api-support = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
only-include = ["src/lintel/users"]

[tool.hatch.build.targets.wheel.sources]
"src" = ""
```

- [ ] **Step 4: Create store module**

Create: `packages/users/src/lintel/users/__init__.py`

```python
"""User management package."""
```

Create: `packages/users/src/lintel/users/py.typed` (empty marker)

Create: `packages/users/src/lintel/users/store.py`

```python
"""In-memory user store."""

from __future__ import annotations

from lintel.domain.types import User


class InMemoryUserStore:
    """Simple in-memory store for users."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def add(self, user: User) -> None:
        self._users[user.user_id] = user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def list_all(self) -> list[User]:
        return list(self._users.values())

    async def update(self, user: User) -> None:
        self._users[user.user_id] = user

    async def remove(self, user_id: str) -> None:
        del self._users[user_id]
```

- [ ] **Step 5: Create routes module**

Create: `packages/users/src/lintel/users/routes.py`

```python
"""User CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import UserCreated, UserRemoved, UserUpdated
from lintel.domain.types import User, UserRole

from lintel.users.store import InMemoryUserStore

router = APIRouter()
user_store_provider = StoreProvider()


class CreateUserRequest(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str = ""
    role: UserRole = UserRole.MEMBER
    slack_user_id: str = ""
    team_ids: list[str] = []


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None


def _user_to_dict(user: User) -> dict[str, Any]:
    data = asdict(user)
    data["team_ids"] = list(user.team_ids)
    return data


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.user_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(
        user_id=body.user_id,
        name=body.name,
        email=body.email,
        role=body.role,
        slack_user_id=body.slack_user_id,
        team_ids=tuple(body.team_ids),
    )
    await store.add(user)
    await dispatch_event(
        request,
        UserCreated(payload={"resource_id": body.user_id, "name": body.name}),
        stream_id=f"user:{body.user_id}",
    )
    return _user_to_dict(user)


@router.get("/users")
async def list_users(
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    users = await store.list_all()
    return [_user_to_dict(u) for u in users]


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_none=True)
    updated = User(**{**asdict(user), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        UserUpdated(payload={"resource_id": user_id, "fields": list(updates.keys())}),
        stream_id=f"user:{user_id}",
    )
    return _user_to_dict(updated)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> None:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await store.remove(user_id)
    await dispatch_event(
        request,
        UserRemoved(payload={"resource_id": user_id, "name": user.name}),
        stream_id=f"user:{user_id}",
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/bamdad/projects/lintel-extraction && uv sync --all-packages && uv run pytest packages/users/tests/ -v`
Expected: 7 PASSED

- [ ] **Step 7: Update app.py to import from new package**

Modify: `packages/app/src/lintel/api/app.py`

Replace the users import line:
- Old: `from lintel.api.routes import ... users ...`
- New: `from lintel.users.routes import router as users_router, user_store_provider`

In `_create_in_memory_stores()` replace:
- Old: `"user_store": InMemoryUserStore(),` (imported from `lintel.api.routes.users`)
- New: `"user_store": InMemoryUserStore(),` (imported from `lintel.users.store`)

In `create_app()` replace:
- Old: `app.include_router(users.router, prefix="/api/v1", tags=["users"])`
- New: `app.include_router(users_router, prefix="/api/v1", tags=["users"])`

In `lifespan()` add after `wire_container(...)`:
```python
from lintel.users.routes import user_store_provider
user_store_provider.override(stores["user_store"])
```

- [ ] **Step 8: Delete old files**

Delete: `packages/app/src/lintel/api/routes/users.py`
Delete: `packages/app/tests/api/test_users.py`

- [ ] **Step 9: Update root pyproject.toml**

Add `packages/users/tests` to `testpaths` and `packages/users/src` to `mypy_path`.

- [ ] **Step 10: Run both package tests and app tests**

Run: `cd /Users/bamdad/projects/lintel-extraction && uv sync --all-packages && uv run pytest packages/users/tests/ -v && uv run pytest packages/app/tests/ -v`
Expected: All pass

- [ ] **Step 11: Add Makefile target**

Add to `Makefile`:
```makefile
test-users: ## Run users package tests
	uv run pytest packages/users/tests/ -v
```

- [ ] **Step 12: Commit**

```bash
cd /Users/bamdad/projects/lintel-extraction
git add packages/users/ packages/app/ pyproject.toml Makefile
git commit -m "feat: extract lintel-users package from app"
```

---

## Chunk 2: Extract Simple CRUD Packages (Batch 1)

All packages in this chunk follow the exact same pattern as `lintel-users`. For each package:

1. Create `packages/<name>/pyproject.toml` (copy users template, change name and `only-include`)
2. Create `packages/<name>/src/lintel/<name>/` with `__init__.py`, `py.typed`, `store.py`, `routes.py`
3. Move store class from `packages/app/src/lintel/api/routes/<route>.py` → `store.py`
4. Move routes + request models from same file → `routes.py`, replacing `@inject` + `Provide[AppContainer.X]` with `Depends(store_provider)`
5. Move tests from `packages/app/tests/api/test_<name>.py` → `packages/<name>/tests/test_routes.py`
6. Create `packages/<name>/tests/conftest.py` with lightweight fixture
7. Update `app.py` imports and add `store_provider.override(...)` in lifespan
8. Delete old route + test files from app
9. Add `packages/<name>/tests` to root `testpaths`, `packages/<name>/src` to `mypy_path`
10. Add `make test-<name>` target
11. Run tests, commit

### Task 3: Extract `lintel-teams`

**Source:** `packages/app/src/lintel/api/routes/teams.py` → `packages/teams/`
**Store:** `InMemoryTeamStore`
**Events:** `TeamCreated`, `TeamUpdated`, `TeamRemoved` (from `lintel.domain.events`)
**Provider name:** `team_store_provider`
**Dependencies:** `lintel-contracts`, `lintel-domain`, `lintel-api-support`, `fastapi`, `pydantic`

- [ ] Step 1: Create package scaffold (pyproject.toml, __init__.py, py.typed)
- [ ] Step 2: Move `InMemoryTeamStore` → `packages/teams/src/lintel/teams/store.py`
- [ ] Step 3: Move routes → `packages/teams/src/lintel/teams/routes.py` (replace DI pattern)
- [ ] Step 4: Create `packages/teams/tests/conftest.py` with lightweight fixture
- [ ] Step 5: Move `test_teams.py` → `packages/teams/tests/test_routes.py`
- [ ] Step 6: Update `app.py` imports + lifespan wiring
- [ ] Step 7: Delete old files from app
- [ ] Step 8: Update root config (testpaths, mypy_path)
- [ ] Step 9: Run `uv run pytest packages/teams/tests/ -v` — all pass
- [ ] Step 10: Commit: `feat: extract lintel-teams package from app`

### Task 4: Extract `lintel-policies-api`

**Source:** `packages/app/src/lintel/api/routes/policies.py` → `packages/policies-api/`
**Store:** `InMemoryPolicyStore`
**Events:** `PolicyCreated`, `PolicyRemoved` (from `lintel.domain.events`)
**Provider name:** `policy_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-policies-api package from app`

### Task 5: Extract `lintel-notifications-api`

**Source:** `packages/app/src/lintel/api/routes/notifications.py` → `packages/notifications-api/`
**Store:** `NotificationRuleStore`
**Events:** `NotificationRuleCreated`, `NotificationRuleRemoved` (from `lintel.domain.events`)
**Provider name:** `notification_rule_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-notifications-api package from app`

### Task 6: Extract `lintel-environments-api`

**Source:** `packages/app/src/lintel/api/routes/environments.py` → `packages/environments-api/`
**Store:** `InMemoryEnvironmentStore`
**Events:** `EnvironmentCreated`, `EnvironmentUpdated`, `EnvironmentRemoved` (from `lintel.domain.events`)
**Provider name:** `environment_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-environments-api package from app`

### Task 7: Extract `lintel-variables-api`

**Source:** `packages/app/src/lintel/api/routes/variables.py` → `packages/variables-api/`
**Store:** `InMemoryVariableStore`
**Events:** `VariableCreated`, `VariableUpdated`, `VariableRemoved` (from `lintel.domain.events`)
**Provider name:** `variable_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-variables-api package from app`

### Task 8: Extract `lintel-credentials-api`

**Source:** `packages/app/src/lintel/api/routes/credentials.py` → `packages/credentials-api/`
**Store:** `InMemoryCredentialStore`
**Events:** `CredentialStored`, `CredentialRevoked` (from `lintel.domain.events`)
**Provider name:** `credential_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-credentials-api package from app`

### Task 9: Extract `lintel-audit-api`

**Source:** `packages/app/src/lintel/api/routes/audit.py` → `packages/audit-api/`
**Store:** `AuditEntryStore`
**Events:** audit events (from `lintel.domain.events`)
**Provider name:** `audit_entry_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-audit-api package from app`

### Task 10: Extract `lintel-approval-requests-api`

**Source:** `packages/app/src/lintel/api/routes/approval_requests.py` → `packages/approval-requests-api/`
**Store:** `InMemoryApprovalRequestStore`
**Events:** `ApprovalRequestCreated`, `ApprovalRequestApproved`, `ApprovalRequestRejected` (from `lintel.domain.events`)
**Provider name:** `approval_request_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-approval-requests-api package from app`

### Task 11: Batch verification

- [ ] Run: `cd /Users/bamdad/projects/lintel-extraction && uv sync --all-packages`
- [ ] Run: `uv run pytest packages/users/tests/ packages/teams/tests/ packages/policies-api/tests/ packages/notifications-api/tests/ packages/environments-api/tests/ packages/variables-api/tests/ packages/credentials-api/tests/ packages/audit-api/tests/ packages/approval-requests-api/tests/ -v`
- [ ] Run: `uv run pytest packages/app/tests/ -v` — remaining app tests pass
- [ ] Run: `uv run ruff check packages/` — no lint errors
- [ ] Commit any fixups

---

## Chunk 3: Extract Medium CRUD Packages (Batch 2)

### Task 12: Extract `lintel-boards`

**Source:** `packages/app/src/lintel/api/routes/boards.py` → `packages/boards/`
**Stores:** `TagStore`, `BoardStore` (both dict-based)
**Events:** `BoardCreated/Updated/Removed`, `TagCreated/Updated/Removed`
**Providers:** `tag_store_provider`, `board_store_provider`
**Extra deps:** `lintel-persistence` (imports `BoardData`, `TagData` from `lintel.persistence.data_models`)

- [ ] Steps 1-10: Same pattern, but two stores and two providers
- [ ] Commit: `feat: extract lintel-boards package from app`

### Task 13: Extract `lintel-triggers-api`

**Source:** `packages/app/src/lintel/api/routes/triggers.py` → `packages/triggers-api/`
**Store:** `InMemoryTriggerStore`
**Provider name:** `trigger_store_provider`

- [ ] Steps 1-10: Same pattern as Task 3
- [ ] Commit: `feat: extract lintel-triggers-api package from app`

### Task 14: Extract `lintel-artifacts-api`

**Source:** `packages/app/src/lintel/api/routes/artifacts.py` → `packages/artifacts-api/`
**Stores:** `CodeArtifactStore`, `TestResultStore`
**Providers:** `code_artifact_store_provider`, `test_result_store_provider`

- [ ] Steps 1-10: Same pattern, two stores
- [ ] Commit: `feat: extract lintel-artifacts-api package from app`

### Task 15: Extract `lintel-projects-api`

**Source:** `packages/app/src/lintel/api/routes/projects.py` → `packages/projects-api/`
**Store:** `ProjectStore`
**Events:** `ProjectCreated/Updated/Removed`
**Provider:** `project_store_provider`

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-projects-api package from app`

### Task 16: Extract `lintel-work-items-api`

**Source:** `packages/app/src/lintel/api/routes/work_items.py` → `packages/work-items-api/`
**Store:** `WorkItemStore`
**Events:** work item events
**Provider:** `work_item_store_provider`

Note: This is a larger file (~512 lines). Follow same pattern but the route file will be bigger.

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-work-items-api package from app`

### Task 17: Extract `lintel-skills-api`

**Source:** `packages/app/src/lintel/api/routes/skills.py` → `packages/skills-api/`
**Store:** `InMemorySkillStore`
**Events:** `SkillRegistered/Updated/Removed/Invoked` (from `lintel.agents.events`)
**Extra deps:** `lintel-agents` (imports `SkillDescriptor`, `SkillCategory`, etc.)
**Provider:** `skill_store_provider`

Also move `packages/app/src/lintel/api/domain/skills/` → `packages/skills-api/src/lintel/skills_api/domain/`
Move domain tests: `packages/app/tests/api/domain/skills/` → `packages/skills-api/tests/`

- [ ] Steps 1-10: Same pattern + domain logic migration
- [ ] Commit: `feat: extract lintel-skills-api package from app`

### Task 18: Extract `lintel-agent-definitions-api`

**Source:** `packages/app/src/lintel/api/routes/agents.py` → `packages/agent-definitions-api/`
**Store:** `AgentDefinitionStore`
**Provider:** `agent_definition_store_provider`
**Extra deps:** `lintel-agents`
**Tests:** both `test_agents.py` and `test_agent_definitions.py`

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-agent-definitions-api package from app`

### Task 19: Extract `lintel-mcp-servers-api`

**Source:** `packages/app/src/lintel/api/routes/mcp_servers.py` → `packages/mcp-servers-api/`
**Store:** `InMemoryMCPServerStore`
**Provider:** `mcp_server_store_provider`

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-mcp-servers-api package from app`

### Task 20: Batch verification

- [ ] Run all new package tests
- [ ] Run remaining app tests
- [ ] Run lint
- [ ] Commit fixups

---

## Chunk 4: Extract Complex CRUD Packages (Batch 3)

### Task 21: Extract `lintel-models-api`

**Source:** `packages/app/src/lintel/api/routes/models.py` → `packages/models-api/`
**Stores:** `InMemoryModelStore`, `InMemoryModelAssignmentStore`
**Providers:** `model_store_provider`, `model_assignment_store_provider`
**Extra deps:** `lintel-models` (for model types)

Note: This route also interacts with `ai_provider_store` for validation. The dependency is via `Depends()` — add an `ai_provider_store_provider` import or pass it as a parameter.

- [ ] Steps 1-10: Same pattern, handle cross-store dependency
- [ ] Commit: `feat: extract lintel-models-api package from app`

### Task 22: Extract `lintel-ai-providers-api`

**Source:** `packages/app/src/lintel/api/routes/ai_providers.py` → `packages/ai-providers-api/`
**Store:** `InMemoryAIProviderStore`
**Provider:** `ai_provider_store_provider`
**Extra deps:** `lintel-models`

This is a larger file (~533 lines) with Ollama integration logic.

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-ai-providers-api package from app`

### Task 23: Extract `lintel-repositories-api`

**Source:** `packages/app/src/lintel/api/routes/repositories.py` → `packages/repositories-api/`
**Store:** Uses `repository_store` (from `lintel-repos` package)
**Provider:** `repository_store_provider`, `repo_provider_provider`

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-repositories-api package from app`

### Task 24: Extract `lintel-workflow-definitions-api`

**Source:** `packages/app/src/lintel/api/routes/workflow_definitions.py` → `packages/workflow-definitions-api/`
**Store:** Uses `pipeline_store` for workflow definitions
**Provider:** `pipeline_store_provider` (shared with pipelines — may need a separate store or import from pipelines package)

- [ ] Steps 1-10: Same pattern, handle shared store
- [ ] Commit: `feat: extract lintel-workflow-definitions-api package from app`

### Task 25: Extract `lintel-settings-api`

**Source:** `packages/app/src/lintel/api/routes/settings.py` → `packages/settings-api/`
**Store:** Uses `variable_store` (shared with variables)
**Provider:** Import `variable_store_provider` from `lintel-variables-api`

- [ ] Steps 1-10: Same pattern, import provider from another extracted package
- [ ] Commit: `feat: extract lintel-settings-api package from app`

### Task 26: Batch verification

- [ ] Run all new package tests
- [ ] Run remaining app tests
- [ ] Run lint + typecheck
- [ ] Commit fixups

---

## Chunk 5: Extract Large/Complex Packages (Batch 4)

### Task 27: Extract `lintel-compliance-api`

**Source:** `packages/app/src/lintel/api/routes/compliance.py` → `packages/compliance-api/`
**Store:** `ComplianceStore` (generic dict store, used for 11 entity types)
**Providers:** One `ComplianceStore` provider per entity (regulation, compliance_policy, procedure, practice, strategy, knowledge_entry, knowledge_extraction, architecture_decision)
**Extra deps:** `lintel-domain` (compliance types/events)

This is the largest file (1,224 lines). The `ComplianceStore` is a generic dict store — move it to `packages/compliance-api/src/lintel/compliance_api/store.py`.

Also move `packages/app/src/lintel/api/domain/compliance_seed.py` into this package.

- [ ] Steps 1-10: Same pattern but with many providers and a large route file
- [ ] Commit: `feat: extract lintel-compliance-api package from app`

### Task 28: Extract `lintel-experimentation-api`

**Source:** `packages/app/src/lintel/api/routes/experimentation.py` → `packages/experimentation-api/`
**Store:** Uses `ComplianceStore` for KPIs, experiments, compliance metrics
**Extra deps:** `lintel-compliance-api` (for `ComplianceStore`)

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-experimentation-api package from app`

### Task 29: Extract `lintel-automations-api`

**Source:** `packages/app/src/lintel/api/routes/automations.py` → `packages/automations-api/`
**Store:** `InMemoryAutomationStore`
**Provider:** `automation_store_provider`
**Also move:** `packages/app/src/lintel/api/domain/automation_scheduler.py` and `packages/app/src/lintel/api/domain/hooks/`
**Domain tests:** `test_automation_scheduler.py`, `test_hook_manager.py`

- [ ] Steps 1-10: Same pattern + domain logic
- [ ] Commit: `feat: extract lintel-automations-api package from app`

### Task 30: Extract `lintel-sandboxes-api`

**Source:** `packages/app/src/lintel/api/routes/sandboxes.py` → `packages/sandboxes-api/`
**Store:** `SandboxStore`
**Provider:** `sandbox_store_provider`, `sandbox_manager_provider`
**Extra deps:** `lintel-sandbox`

- [ ] Steps 1-10: Same pattern
- [ ] Commit: `feat: extract lintel-sandboxes-api package from app`

### Task 31: Extract `lintel-pipelines-api`

**Source:** `packages/app/src/lintel/api/routes/pipelines.py` → `packages/pipelines-api/`
**Store:** `InMemoryPipelineStore`
**Provider:** `pipeline_store_provider`
**Also move:** `packages/app/src/lintel/api/domain/delivery_loop/`
**Domain tests:** `test_delivery_loop.py`
**Extra deps:** `lintel-workflows` (for `PipelineRun`, `Stage`, etc.)

This is the second largest (867 lines) with SSE streaming and stage management.

- [ ] Steps 1-10: Same pattern + domain logic + SSE
- [ ] Commit: `feat: extract lintel-pipelines-api package from app`

### Task 32: Extract `lintel-chat-api`

**Source:** `packages/app/src/lintel/api/routes/chat.py` → `packages/chat-api/`
**Store:** `ChatStore`
**Provider:** `chat_store_provider`, `chat_router_provider`, `command_dispatcher_provider`
**Also move:** `packages/app/src/lintel/api/domain/chat_router.py`
**Tests:** `test_chat.py`, `test_chat_project_selection.py`, `test_chat_retry.py`, `test_chat_router.py`
**Extra deps:** `lintel-workflows`, `lintel-models`, `lintel-agents`

This is the most complex extraction (1,097 lines route + 800 lines chat_router). The chat router has LLM integration and workflow dispatch logic.

- [ ] Steps 1-10: Same pattern + domain logic + streaming
- [ ] Commit: `feat: extract lintel-chat-api package from app`

### Task 33: Batch verification

- [ ] Run all package tests
- [ ] Run remaining app tests
- [ ] Run lint + typecheck
- [ ] Commit fixups

---

## Chunk 6: Cleanup and Finalization

### Task 34: Update app package dependencies

**Files:**
- Modify: `packages/app/pyproject.toml` — add all extracted packages as dependencies
- Modify: `packages/app/src/lintel/api/container.py` — remove store providers that moved to packages, keep only domain service providers
- Modify: `packages/app/tests/conftest.py` — update store imports to new locations

- [ ] Step 1: Add all `lintel-*-api` packages to app's dependencies
- [ ] Step 2: Update container.py — remove entity store providers, keep domain services
- [ ] Step 3: Update test conftest imports
- [ ] Step 4: Run `uv run pytest packages/app/tests/ -v` — pass
- [ ] Step 5: Commit: `refactor: update app package dependencies for extracted packages`

### Task 35: Update root pyproject.toml

**Files:**
- Modify: `pyproject.toml` — add all new package test paths and mypy paths

- [ ] Step 1: Add all `packages/<name>/tests` entries to `testpaths`
- [ ] Step 2: Add all `packages/<name>/src` entries to `mypy_path`
- [ ] Step 3: Run `uv run mypy -p lintel.users -p lintel.teams` (spot check)
- [ ] Step 4: Commit: `chore: add extracted packages to workspace config`

### Task 36: Update Makefile

**Files:**
- Modify: `Makefile`

- [ ] Step 1: Add `test-<name>` target for every extracted package
- [ ] Step 2: Update `test-unit` to include all new package test paths
- [ ] Step 3: Update `test-postgres` similarly
- [ ] Step 4: Update `.PHONY` line
- [ ] Step 5: Run `make test-users` — passes
- [ ] Step 6: Run `make test-unit` — all pass
- [ ] Step 7: Commit: `chore: add Makefile targets for extracted packages`

### Task 37: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] Step 1: Add new packages to the workspace table
- [ ] Step 2: Update the commands section with new test targets
- [ ] Step 3: Update import rules section
- [ ] Step 4: Commit: `docs: update CLAUDE.md with extracted packages`

### Task 38: Full CI verification

- [ ] Step 1: Run `make lint` — pass
- [ ] Step 2: Run `make typecheck` — pass
- [ ] Step 3: Run `make test-unit` — all pass
- [ ] Step 4: Run `make test-app` — pass (only remaining app tests)
- [ ] Step 5: Commit any final fixups
- [ ] Step 6: Final commit: `chore: app package extraction complete`
