# App Package Extraction — One Package Per CRUD Entity

**Date:** 2026-03-15
**Status:** Draft

## Problem

`packages/app/` is a monolith containing 40 route modules, 18 domain modules, and 50+ test files (~8K lines). Any change triggers all ~400 tests. A simple edit to `users.py` runs compliance, pipelines, chat, and every other test.

## Goal

Extract every CRUD entity into its own package so that:
- `make test-users` runs only user tests (~5 tests, <1s)
- A change to `packages/users/` doesn't trigger `packages/teams/` tests
- `packages/app/` becomes a thin composition root: lifespan, DI wiring, middleware, MCP exposure

## Packages to Extract

Each route module that owns a store becomes its own package. 30 packages total:

| Package | Source Route | Store Class | Domain Events | Tests |
|---------|-------------|-------------|---------------|-------|
| `lintel-users` | `users.py` | `InMemoryUserStore` | `UserCreated/Updated/Removed` | `test_users.py` |
| `lintel-teams` | `teams.py` | `InMemoryTeamStore` | `TeamCreated/Updated/Removed` | `test_teams.py` |
| `lintel-projects-api` | `projects.py` | `ProjectStore` | `ProjectCreated/Updated/Removed` | `test_projects.py` |
| `lintel-boards` | `boards.py` | `TagStore`, `BoardStore` | `BoardCreated/Updated/Removed`, `TagCreated/Updated/Removed` | `test_boards.py` |
| `lintel-work-items` | `work_items.py` | `WorkItemStore` | `WorkItemCreated/Updated/Removed` | `test_work_items.py` |
| `lintel-pipelines-api` | `pipelines.py` | `InMemoryPipelineStore` | pipeline events | `test_pipelines.py` |
| `lintel-chat-api` | `chat.py` | `ChatStore` | `ConversationCreated` etc. | `test_chat.py`, `test_chat_project_selection.py`, `test_chat_retry.py` |
| `lintel-compliance-api` | `compliance.py` | `ComplianceStore` (generic) | compliance events | `test_compliance.py` |
| `lintel-ai-providers` | `ai_providers.py` | `InMemoryAIProviderStore` | provider events | `test_ai_providers.py` |
| `lintel-models-api` | `models.py` | `InMemoryModelStore`, `InMemoryModelAssignmentStore` | model events | `test_models.py` |
| `lintel-credentials-api` | `credentials.py` | `InMemoryCredentialStore` | credential events | `test_credentials.py` |
| `lintel-environments-api` | `environments.py` | `InMemoryEnvironmentStore` | environment events | `test_environments.py` |
| `lintel-triggers-api` | `triggers.py` | `InMemoryTriggerStore` | trigger events | `test_triggers.py` |
| `lintel-variables-api` | `variables.py` | `InMemoryVariableStore` | variable events | `test_variables.py` |
| `lintel-policies-api` | `policies.py` | `InMemoryPolicyStore` | policy events | `test_policies.py` |
| `lintel-notifications-api` | `notifications.py` | `NotificationRuleStore` | notification events | `test_notifications.py` |
| `lintel-audit-api` | `audit.py` | `AuditEntryStore` | audit events | `test_audit.py` |
| `lintel-artifacts-api` | `artifacts.py` | `CodeArtifactStore`, `TestResultStore` | artifact events | `test_artifacts.py` |
| `lintel-approval-requests-api` | `approval_requests.py` | `InMemoryApprovalRequestStore` | approval events | `test_approval_requests.py` |
| `lintel-skills-api` | `skills.py` | `InMemorySkillStore` | skill events | `test_skills.py` |
| `lintel-mcp-servers-api` | `mcp_servers.py` | `InMemoryMCPServerStore` | — | `test_mcp_servers.py` |
| `lintel-sandboxes-api` | `sandboxes.py` | `SandboxStore` | sandbox events | `test_sandboxes.py` |
| `lintel-workflow-definitions-api` | `workflow_definitions.py` | — (uses pipeline_store) | — | `test_workflow_definitions.py` |
| `lintel-automations-api` | `automations.py` | `InMemoryAutomationStore` | automation events | `test_automations.py` |
| `lintel-experimentation-api` | `experimentation.py` | uses ComplianceStore | experimentation events | `test_experimentation.py` |
| `lintel-settings-api` | `settings.py` | — (uses variable_store) | — | `test_settings.py` |
| `lintel-repositories-api` | `repositories.py` | — (uses repository_store) | repository events | `test_repositories.py` |
| `lintel-agent-definitions-api` | `agents.py` | `AgentDefinitionStore` | agent events | `test_agents.py`, `test_agent_definitions.py` |

**Not extracted** (stay in `app`):
- `health.py` — 15 lines, no store
- `threads.py` — 18 lines, no store
- `approvals.py` — 76 lines, thin wrapper, no own store
- `streams.py` — 60 lines, SSE helper
- `events.py` — reads from event_store (no own entity)
- `metrics.py` — reads from projections (no own entity)
- `pii.py` — thin wrapper around `lintel-pii` package
- `onboarding.py` — 35 lines, reads from other stores
- `debug.py` — orchestration tool, reads from multiple stores
- `admin.py` — admin operations across stores

**Domain modules** (stay in `app` or extract separately):
- `domain/chat_router.py` → moves into `lintel-chat-api`
- `domain/event_dispatcher.py` → moves into `lintel-contracts` or new `lintel-api-support` shared package
- `domain/seed.py` → stays in `app` (seeds across stores)
- `domain/command_dispatcher.py` → stays in `app`
- `domain/automation_scheduler.py` → moves into `lintel-automations-api`
- `domain/pipeline_scheduler.py` → stays in `app` (cross-cutting)
- `domain/scheduler_loop.py` → stays in `app`
- `domain/trigger_handler.py` → stays in `app`
- `domain/version_resolver.py` → stays in `app`
- `domain/delivery_loop/` → moves into `lintel-pipelines-api` or stays in `app`
- `domain/hooks/` → moves into `lintel-automations-api`
- `domain/skills/` → moves into `lintel-skills-api`

## Package Structure

Each extracted package follows this layout:

```
packages/users/
├── pyproject.toml
├── src/
│   └── lintel/
│       └── users/
│           ├── py.typed
│           ├── store.py        # InMemoryUserStore
│           └── routes.py       # router + request/response models
└── tests/
    ├── conftest.py             # lightweight test fixtures
    └── test_routes.py          # HTTP tests against isolated app
```

### pyproject.toml template

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

[project.optional-dependencies]
test = [
    "pytest>=8",
    "httpx>=0.27",
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

### DI Strategy: `lintel-api-support` shared package

A new tiny package `packages/api-support/` provides:

1. **`dispatch_event`** — moved from `app/domain/event_dispatcher.py`
2. **`StoreProvider`** — a simple container-free DI mechanism for stores

```python
# packages/api-support/src/lintel/api_support/provider.py
from __future__ import annotations
from typing import Any

class StoreProvider:
    """Minimal store holder that can be overridden at app startup."""

    def __init__(self) -> None:
        self._instance: Any = None

    def override(self, instance: Any) -> None:
        self._instance = instance

    def __call__(self) -> Any:
        if self._instance is None:
            raise RuntimeError("Store not configured — call .override() first")
        return self._instance
```

Each extracted package declares its store provider at module level:

```python
# packages/users/src/lintel/users/routes.py
from lintel.api_support.provider import StoreProvider

user_store_provider = StoreProvider()

@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),
) -> dict[str, Any]:
    ...
```

The `app` package wires everything at startup:

```python
# app.py lifespan
from lintel.users.routes import user_store_provider
user_store_provider.override(stores["user_store"])
```

This removes the dependency on `dependency-injector` for extracted packages. The `app` package can still use `AppContainer` internally for domain services.

### Test Fixtures

Each package has its own lightweight `conftest.py`:

```python
# packages/users/tests/conftest.py
from collections.abc import Generator
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.users.store import InMemoryUserStore
from lintel.users.routes import router, user_store_provider

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

Tests that need event dispatch will mock it or use a no-op event store.

## What `packages/app/` Becomes

After extraction, `app` contains:
- `app.py` — FastAPI app creation, lifespan, store construction, DI wiring
- `container.py` — AppContainer for domain services (executor, chat_router, etc.)
- `middleware.py` — CorrelationMiddleware
- `routes/` — only the ~10 non-extracted thin routes (health, threads, approvals, streams, events, metrics, pii, onboarding, debug, admin)
- `domain/` — seed.py, command_dispatcher, pipeline_scheduler, scheduler_loop, trigger_handler, version_resolver

`app` depends on all extracted packages and imports their routers:

```python
from lintel.users.routes import router as users_router
app.include_router(users_router, prefix="/api/v1", tags=["users"])
```

## Makefile Changes

Add a `test-<pkg>` target per extracted package:

```makefile
test-users: ## Run users package tests
	uv run pytest packages/users/tests -x -q

test-teams: ## Run teams package tests
	uv run pytest packages/teams/tests -x -q

# ... etc for all 30 packages
```

Update `test-unit` to run all package tests in parallel.

## Migration Strategy

### Phase 1: Foundation
1. Create `packages/api-support/` with `StoreProvider` and `dispatch_event`
2. Add to workspace `pyproject.toml`
3. Verify existing tests still pass

### Phase 2: Extract one package as proof-of-concept
1. Extract `lintel-users` (simplest CRUD, ~150 lines)
2. Move store to `packages/users/src/lintel/users/store.py`
3. Move routes to `packages/users/src/lintel/users/routes.py`
4. Move tests to `packages/users/tests/test_routes.py`
5. Update `app.py` to import from new location
6. Verify both `make test-users` and `make test-app` pass

### Phase 3: Extract remaining packages
Extract in order of simplicity (small → large):
1. teams, policies, notifications, environments, variables, credentials
2. boards, triggers, artifacts, audit, approval-requests
3. projects, work-items, skills, agent-definitions, mcp-servers
4. models, ai-providers, repositories, workflow-definitions, settings
5. automations (with hooks + scheduler), experimentation
6. sandboxes, pipelines (with delivery-loop), chat (with chat-router)

### Phase 4: Cleanup
1. Remove moved code from `packages/app/`
2. Update `app` dependencies to depend on extracted packages
3. Update CLAUDE.md with new package list
4. Update `test-unit` and `test-affected` targets

## Event Dispatch in Extracted Packages

Routes currently do:
```python
await dispatch_event(request, UserCreated(...), stream_id=f"user:{id}")
```

This requires `request.app.state.event_store`. In extracted packages, the `dispatch_event` function moves to `lintel-api-support` and keeps the same signature — it reads from `request.app.state` which is set by the `app` lifespan. No change needed in the function itself, just the import path.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| 30 new packages = boilerplate | Script to scaffold packages from template |
| Import path changes break things | Search-and-replace + `test-affected` catches issues |
| Circular deps between packages | Extracted packages depend only on contracts/domain/api-support, never on each other |
| `dependency-injector` wiring breaks | Extracted packages use simple `StoreProvider`, not DI container |
| Postgres store construction in `app.py` | Stays in `app.py` — only in-memory stores move to packages |

## Success Criteria

- [ ] `make test-users` runs ~5 tests in <1s
- [ ] Changing `packages/users/` does NOT trigger `packages/teams/` tests
- [ ] `make test-app` runs only app-level tests (admin, debug, metrics, etc.)
- [ ] `make all` still passes (full CI check)
- [ ] No import of `lintel.api.container` from extracted packages
