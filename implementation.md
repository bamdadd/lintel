# Implementation Log

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
