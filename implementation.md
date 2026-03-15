# Implementation Log

## Phase 5: Extract 6 Large/Complex Packages

### Completed Steps
1. Fixed `StoreProvider.__class_getitem__` to support generic subscript `StoreProvider[T]` notation
2. Added `test_sandboxes.py` to `sandboxes-api/tests/` (was missing), updating import to `lintel.sandboxes_api.routes`
3. Added `client` fixture to `chat-api/tests/conftest.py` for `test_chat_project_selection.py` and `test_chat_retry.py`
4. Ran ruff auto-fix (59 import-sort issues) across all 6 packages
5. Committed all 6 packages + app wiring — committed as `0fd4a71`

### Deviations from Plan
- All 6 packages were already scaffolded (routes, stores, domain logic, tests) when work began — the main gaps were `StoreProvider` subscript support, the missing sandboxes test file, and the missing chat conftest fixture.

### Files Created
- `packages/compliance-api/` — ComplianceStore, routes, seed, 14 tests
- `packages/experimentation-api/` — uses ComplianceStore, routes, 9 tests
- `packages/automations-api/` — InMemoryAutomationStore, routes, scheduler, hooks, 48 tests
- `packages/sandboxes-api/` — SandboxStore, routes, 11 tests
- `packages/pipelines-api/` — InMemoryPipelineStore, routes, delivery_loop, 26+ tests
- `packages/chat-api/` — ChatStore, routes, chat_router, 110+ tests

### Files Modified
- `packages/api-support/src/lintel/api_support/provider.py` — added `__class_getitem__` for generic subscript support
- `packages/app/src/lintel/api/app.py` — wired all 6 new packages via StoreProvider.override()
- `packages/app/pyproject.toml` — added 6 new dependencies
- `packages/app/tests/conftest.py` — updated stale imports to new package paths
- `pyproject.toml` — added 6 new test/src paths

### Test Results
- 218 tests passing across all 6 new packages
- 388 app tests passing, 59 skipped — no regressions

---

## Phase 4: Extract Medium CRUD Batch (8 packages)

### Completed Steps
1. Created `lintel-boards` package with `TagStore`, `BoardStore`, routes — committed as `cbceef8`
2. Created `lintel-triggers-api` package with `InMemoryTriggerStore`, routes — committed as `ea9494c`
3. Created `lintel-artifacts-api` package with `CodeArtifactStore`, `TestResultStore`, routes — committed as `01d5e60`
4. Created `lintel-projects-api` package with `ProjectStore`, routes — committed as `6e90009`
5. Created `lintel-work-items-api` package with `WorkItemStore`, routes — committed as `55684fd`
6. Created `lintel-skills-api` package with `InMemorySkillStore`, routes, and moved `domain/skills/` — committed as `30ea09e`
7. Created `lintel-agent-definitions-api` package with `AgentDefinitionStore`, routes — committed as `62bc05b`
8. Created `lintel-mcp-servers-api` package with `InMemoryMCPServerStore`, routes — committed as `5dffa70`
9. Wired all 8 packages into app, updated pyproject files, fixed stale imports — committed as `8f2d9ac`

### Deviations from Plan
- Fixed pre-existing stale imports in workflow tests (`test_policy.py` → `lintel.policies_api.store`, `test_setup_workspace.py` → `lintel.variables_api.store`)
- Added `lintel-skills-api` as a dependency to `lintel-workflows` (workflows nodes import `discover_test_command`)

### Files Created (new packages)
- `packages/boards/` — `TagStore`, `BoardStore`, routes, 11 tests
- `packages/triggers-api/` — `InMemoryTriggerStore`, routes, 6 tests
- `packages/artifacts-api/` — `CodeArtifactStore`, `TestResultStore`, routes, 9 tests
- `packages/projects-api/` — `ProjectStore`, routes, 10 tests
- `packages/work-items-api/` — `WorkItemStore`, routes, 8 tests
- `packages/skills-api/` — `InMemorySkillStore`, routes, domain skills, 29 tests
- `packages/agent-definitions-api/` — `AgentDefinitionStore`, routes, 13 tests
- `packages/mcp-servers-api/` — `InMemoryMCPServerStore`, routes, 8 tests

### Test Results
- All 8 new packages: 100 tests passing
- `packages/app/tests/`: 388 passed, 59 skipped
- `packages/workflows/tests/`: 276 passed (1 pre-existing failure in `test_setup_workspace`)



## Phase 1: Protocol + Docker backend execute_stream (Tasks 1 & 2)

### Completed Steps
1. Added `execute_stream` method to `SandboxManager` protocol with docstring and `yield ""` stub — committed as `1b53c55`
2. Created `packages/contracts/tests/test_execute_stream_protocol.py` with conformance tests — committed as `1b53c55`
3. Added `AsyncIterator` to `TYPE_CHECKING` import block in `docker_backend.py` — committed as `9531e6a`
4. Implemented `execute_stream` in `DockerSandboxManager` using low-level `exec_create`/`exec_start(demux=True)` — committed as `9531e6a`
5. Created `packages/infrastructure/tests/sandbox/test_docker_streaming.py` with 8 tests — committed as `9531e6a`

### Deviations from Plan
- None

### Files Created
- `/Users/bamdad/projects/lintel/packages/contracts/tests/test_execute_stream_protocol.py` — protocol conformance tests
- `/Users/bamdad/projects/lintel/packages/infrastructure/tests/sandbox/test_docker_streaming.py` — Docker streaming tests

### Files Modified
- `/Users/bamdad/projects/lintel/packages/contracts/src/lintel/contracts/protocols.py:200-218` — added `execute_stream` method to `SandboxManager`
- `/Users/bamdad/projects/lintel/packages/infrastructure/src/lintel/infrastructure/sandbox/docker_backend.py:16-17,203-268` — added `AsyncIterator` import and `execute_stream` implementation

### Test Results
- contracts: 106 tests passing
- infrastructure: 372 passed, 7 skipped

### Notes for Reviewer
- `execute_stream` returns `_stream()` (inner async generator) eagerly — setup (exec_create, exec_start) happens synchronously at call time; only iteration is lazy. This matches the plan's design note.
- Per-chunk timeout uses `asyncio.wait_for` wrapping `asyncio.to_thread(_next_chunk)`. On timeout, raises `SandboxTimeoutError`.
- The protocol stub uses `yield ""` (like `stream_model` does) rather than `...` because the method is an async generator in the protocol definition.

---

## Phase 3: Extract Simple CRUD Batch (8 packages)

### Completed Steps
1. Extracted `lintel-teams` — committed as `2c6ffe9`
2. Extracted `lintel-policies-api` — committed as `4191d32`
3. Extracted `lintel-notifications-api` — committed as `a3c62e5`
4. Extracted `lintel-environments-api` — committed as `a1a542a`
5. Extracted `lintel-variables-api` — committed as `25944f7`
6. Extracted `lintel-credentials-api` — committed as `c907e0a`
7. Extracted `lintel-audit-api` — committed as `deaf3a6`
8. Extracted `lintel-approval-requests-api` — committed as `9642174`

### Deviations from Plan
- `lintel-credentials-api` depends on `lintel-persistence` (not just domain) because it imports `Credential`, `CredentialType` from `lintel.persistence.types` and `CredentialStored`, `CredentialRevoked` from `lintel.persistence.events`.
- `lintel-audit-api` routes.py does not import `dispatch_event` — the original `audit.py` had no event dispatching.
- `approval_requests.py` originally used a request-based store getter pattern — converted to `StoreProvider` pattern to match all other extracted packages.

### Files Created
- `packages/teams/` — lintel-teams package
- `packages/policies-api/` — lintel-policies-api package
- `packages/notifications-api/` — lintel-notifications-api package
- `packages/environments-api/` — lintel-environments-api package
- `packages/variables-api/` — lintel-variables-api package
- `packages/credentials-api/` — lintel-credentials-api package
- `packages/audit-api/` — lintel-audit-api package
- `packages/approval-requests-api/` — lintel-approval-requests-api package

### Test Results
- All 8 extracted packages: all tests passing (teams: 5, policies: 5, notifications: 5, environments: 8, variables: 6, credentials: 11, audit: 5, approval-requests: 6)
- App test suite: 491 passed, 67 skipped — no regressions

---

## Import Migration: lintel.infrastructure.* → new package paths

### Completed Steps
1. Updated all `lintel.infrastructure.*` imports in consumer packages to use new extracted package paths.

### Files Modified
- `packages/app/src/lintel/api/app.py` — 10 top-level imports + 4 inline imports updated
- `packages/app/src/lintel/api/deps.py` — 5 imports updated
- `packages/app/src/lintel/api/routes/admin.py` — 3 imports updated (1 top-level, 2 inline)
- `packages/app/src/lintel/api/routes/events.py` — 2 imports updated (1 top-level, 1 inline)
- `packages/app/src/lintel/api/routes/repositories.py` — 1 import updated
- `packages/app/src/lintel/api/routes/workflows.py` — 1 import updated
- `packages/app/src/lintel/api/routes/threads.py` — 1 import updated
- `packages/app/src/lintel/api/routes/debug.py` — 1 inline import updated
- `packages/app/src/lintel/api/domain/chat_router.py` — 1 import updated
- `packages/app/src/lintel/api/domain/scheduler_loop.py` — 1 import updated
- `packages/app/tests/conftest.py` — 2 imports updated
- `packages/app/tests/api/test_admin_projections.py` — 1 import updated
- `packages/workflows/src/lintel/workflows/nodes/close.py` — 1 inline import updated
- `packages/workflows/tests/workflows/test_close_node.py` — 3 @patch paths updated
- `packages/models/tests/models/test_claude_code_streaming.py` — 3 @patch paths updated
- `packages/sandbox/tests/sandbox/test_docker_streaming.py` — 1 @patch path updated
- `tests/e2e/test_claude_code_sandbox.py` — 1 import updated
- `tests/integration/test_event_store.py` — 1 import updated
- `tests/integration/test_pii_pipeline.py` — 3 imports updated
- `tests/integration/test_postgres_chat_store.py` — 1 import updated
- `tests/integration/test_pii_vault.py` — 1 import updated
- `tests/integration/test_full_pipeline.py` — 3 imports updated
- `tests/integration/test_workflow_lifecycle.py` — 3 imports updated
- `tests/integration/sandbox/conftest.py` — 1 inline import updated

### Deviations from Plan
- None. Files inside `packages/infrastructure/` and `packages/domain/` were left untouched as specified.
- `lintel.infrastructure.mcp` references kept as-is (MCP stays in infrastructure per the task spec).
