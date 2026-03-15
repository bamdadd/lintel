# File Decomposition & Dead Code Cleanup

**Date:** 2026-03-15
**Status:** Draft

## Problem

Several files have grown too large (800–1,600 lines), and 4 dead files remain from incomplete package extraction. The Makefile's `head -100` truncation caused a pipeline failure (lint target on line 165 was missed).

## Phases

### Phase 1: Dead File Cleanup

Delete 4 orphaned files and fix imports to point at canonical sources.

**Files to delete:**
- `packages/app/src/lintel/api/domain/seed.py` (1,639 lines) — duplicate of `lintel.domain.seed`
- `packages/domain/src/lintel/domain/workflow_executor.py` (1,063 lines) — duplicate of `lintel.workflows.workflow_executor`
- `packages/app/src/lintel/api/routes/chat.py` (1,097 lines) — extracted to `lintel.chat_api.routes`
- `packages/app/src/lintel/api/routes/compliance.py` (1,224 lines) — extracted to `lintel.compliance_api.routes`

**Import rewrites:**
- `lintel.api.app` line 210: `from lintel.api.domain.seed` → `from lintel.domain.seed`
- `lintel.api.routes.workflow_definitions` line 55: same
- `lintel.api.routes.pipelines` line 35: same
- `lintel.pipelines_api.routes` line 34: same
- `packages/app/tests/api/domain/test_seed.py` line 5: same
- `packages/domain/tests/domain/test_policy_enforcement.py` line 10: `from lintel.domain.workflow_executor` → `from lintel.workflows.workflow_executor`
- `packages/domain/tests/domain/test_workflow_executor_continuation.py` line 8: same
- `packages/domain/tests/domain/test_workflow_executor.py` line 12: same
- `packages/workflows/src/lintel/workflows/nodes/_notifications.py` line 10: `from lintel.api.routes.chat` → `from lintel.chat_api.routes` (or `from lintel.chat_api.chat_router`)
- `packages/workflows/tests/workflows/test_notifications.py` lines 47, 94: same

**Verify:** `make test-affected BASE_REF=HEAD~1`

---

### Phase 2: Split Makefile

Split `Makefile` (225 lines) into included fragments. GNU Make supports `include`.

**New structure:**
```
Makefile              # ~30 lines: includes + help + install + all + dev
mk/
  tests.mk            # Per-package test targets (lines 9–163)
  quality.mk          # lint, typecheck, format (lines 165–175)
  server.mk           # serve, serve-db, db-up, db-down, migrate (lines 177–197)
  ui.mk               # ui-install, ui-dev, ui-build, ui-generate, ui-test (lines 201–214)
  ollama.mk            # ollama-pull, ollama-serve (lines 219–224)
```

**Verify:** `make help`, `make lint`, `make test-contracts`

---

### Phase 3: Split seed.py (1,639 → 3 files)

Split `packages/domain/src/lintel/domain/seed.py` into:

| File | Content | ~Lines |
|------|---------|--------|
| `seed_agents.py` | `DEFAULT_AGENTS` tuple (lines 23–250) | ~230 |
| `seed_skills.py` | `DEFAULT_SKILLS` tuple (lines 251–752) | ~500 |
| `seed_workflows.py` | `DEFAULT_WORKFLOWS` tuple (lines 753–1639) | ~890 |
| `seed.py` | Re-export barrel: imports + `__all__` | ~15 |

The barrel `seed.py` preserves all existing import paths (`from lintel.domain.seed import DEFAULT_AGENTS`).

**Verify:** `make test-app`

---

### Phase 4: Split implement.py (1,506 → 4 files)

Split `packages/workflows/src/lintel/workflows/nodes/implement.py` into:

| File | Content | ~Lines |
|------|---------|--------|
| `implement.py` | `spawn_implementation()` entry point + `_stream_execute_with_logging` + `_resolve_coder_policy` | ~350 |
| `_impl_tdd.py` | `_implement_tdd()` — TDD implementation strategy | ~225 |
| `_impl_structured.py` | `_implement_structured()` — structured implementation strategy | ~160 |
| `_impl_discovery.py` | `_discover_dev_commands()`, `_load_skill_system_prompt()`, `_read_guidelines()`, `_pre_read_plan_files()`, `_log_test_output()` | ~500 |

All helpers imported into `implement.py` so external callers (`from lintel.workflows.nodes.implement import spawn_implementation`) are unchanged.

**Verify:** `make test-workflows`

---

### Phase 5: Split compliance_api/routes.py (1,140 → 5 files)

Split `packages/compliance-api/src/lintel/compliance_api/routes.py` by resource domain:

| File | Content | ~Lines |
|------|---------|--------|
| `routes.py` | Router barrel — creates `router`, includes sub-routers, shared providers | ~60 |
| `regulations.py` | Regulation CRUD + templates | ~150 |
| `policies.py` | Compliance policy + procedure + practice + strategy CRUD | ~350 |
| `knowledge.py` | Knowledge entry + extraction CRUD | ~200 |
| `architecture.py` | Architecture decision CRUD | ~150 |
| `config.py` | Compliance config + overview endpoint | ~100 |

Each sub-file defines its own `router = APIRouter()`. The barrel `routes.py` includes them all under the existing prefix so MCP/app mounting is unchanged.

**Verify:** `make test-compliance-api`

---

### Phase 6: Split chat_api/routes.py (1,100 → 3 files)

Split `packages/chat-api/src/lintel/chat_api/routes.py`:

| File | Content | ~Lines |
|------|---------|--------|
| `store.py` | `ChatStore` class (line 73–~200) | ~130 |
| `streaming.py` | `send_message_stream()`, `stream_conversation_events()` — SSE endpoints | ~200 |
| `routes.py` | Remaining CRUD routes + barrel imports + router | ~770 |

`ChatStore` is a standalone class with no route dependencies — clean extraction. Streaming endpoints are self-contained SSE handlers.

**Verify:** `make test-chat-api`

---

### Phase 7: Split workflow_executor.py (1,063 → 3 files)

Split `packages/workflows/src/lintel/workflows/workflow_executor.py`:

| File | Content | ~Lines |
|------|---------|--------|
| `workflow_executor.py` | `WorkflowExecutor` class — `__init__`, `execute()`, `resume()`, `_stream_graph()`, `_build_config()` | ~400 |
| `_executor_artifacts.py` | `_artifact_lookup_node_output()`, `_import_artifact()`, `_emit_artifact_event()`, `_prepare_tool_manifest()` | ~200 |
| `_executor_lifecycle.py` | `_mark_stage_completed()`, `_send_stage_notification()`, `_emit_event()`, `_get_node_metadata()`, `_read_node_code()`, `_log_error()`, `_check_capacity_for_next_stage()`, `_on_workflow_interrupted()`, `_auto_promote_if_capacity()` | ~400 |

Helper modules contain standalone functions that take `WorkflowExecutor` fields as parameters (not methods). `workflow_executor.py` imports and calls them.

**Verify:** `make test-workflows`

---

### Phase 8: Split app.py (882 → 4 files)

Split `packages/app/src/lintel/api/app.py`:

| File | Content | ~Lines |
|------|---------|--------|
| `app.py` | `create_app()` — creates FastAPI, adds middleware, includes routers | ~100 |
| `lifespan.py` | `lifespan()` async context manager — store creation, event bus, projections | ~300 |
| `store_wiring.py` | All `StoreProvider.override()` calls + store factory functions | ~300 |
| `routers.py` | All `include_router()` calls grouped by domain | ~150 |

**Verify:** `make test-app`

---

## Execution Order

Phases 1–2 are independent. Phases 3–8 are independent of each other but depend on Phase 1.

```
Phase 1 (dead files) ──┬──→ Phase 3 (seed)
                       ├──→ Phase 4 (implement)
Phase 2 (Makefile) ────├──→ Phase 5 (compliance)
                       ├──→ Phase 6 (chat)
                       ├──→ Phase 7 (executor)
                       └──→ Phase 8 (app)
```

Each phase ends with the relevant `make test-*` target. Final validation: `make all`.

## Non-Goals

- No new features or behavior changes
- No dependency changes between packages
- No test restructuring (beyond fixing imports)
