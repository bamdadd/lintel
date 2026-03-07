# Codebase Survey - react-ui

## Survey Scope

**Tech Area:** react-ui
**Task Context:** Build a React SPA web dashboard (Lintel UI) that serves as the control plane for managing agents, workflows, connections, repositories, and observability for an AI collaboration infrastructure platform.
**Survey Date:** 2026-03-06
**Configuration Source:** Fallback (no `docs/tech-stack/react-ui.yaml` manifest found). Tech stack inferred from `todos/2026-03-06-create-ui/index.md` planning document.

---

## Discovered Frameworks

There is **no existing frontend code in this repository**. The `ui/` directory does not exist. The `.gitignore` has no Node.js or frontend entries. No `package.json`, `vite.config`, `tsconfig.json`, or any `*.tsx`/`*.jsx` files were found anywhere in the repo.

The tech stack below is the **planned** stack documented in the task index, not yet scaffolded:

| Framework | Version | Source |
|-----------|---------|--------|
| React | 18 | `todos/2026-03-06-create-ui/index.md` |
| TypeScript | latest | `todos/2026-03-06-create-ui/index.md` |
| Mantine | v7 | `todos/2026-03-06-create-ui/index.md` |
| React Router | v7 | `todos/2026-03-06-create-ui/index.md` |
| TanStack Query | v5 | `todos/2026-03-06-create-ui/index.md` |
| React Flow | latest | `todos/2026-03-06-create-ui/index.md` |
| Recharts (via Mantine Charts) | latest | `todos/2026-03-06-create-ui/index.md` |
| Vite | latest | `todos/2026-03-06-create-ui/index.md` |

---

## Architecture Overview

### Directory Structure

```
lintel/                          (repo root)
├── src/lintel/                  (Python backend -- all existing code lives here)
│   ├── api/
│   │   ├── app.py               # FastAPI application factory
│   │   ├── deps.py              # Dependency injection helpers
│   │   ├── middleware/          # CorrelationMiddleware
│   │   └── routes/              # 16 route modules (52 endpoints total)
│   ├── contracts/               # Pure domain types, events, commands, protocols
│   ├── infrastructure/          # Concrete implementations
│   ├── workflows/               # LangGraph orchestration
│   ├── agents/                  # Agent runtime
│   ├── skills/                  # Skill registry
│   └── projections/             # CQRS read-side
├── tests/                       # pytest suite (unit, integration, e2e)
├── todos/2026-03-06-create-ui/
│   └── index.md                 # Full UI spec (pages, UX, API map, file structure)
├── pyproject.toml               # Python project config
├── Makefile                     # Build targets (Python only)
├── .gitignore                   # Python-only ignores
└── ui/                          # DOES NOT EXIST -- greenfield
```

Planned UI structure (from `todos/2026-03-06-create-ui/index.md`):

```
ui/
  index.html
  vite.config.ts
  tsconfig.json
  package.json
  src/
    main.tsx
    App.tsx
    api/
      client.ts
      hooks/          # TanStack Query hooks per domain
    components/
      layout/         # AppShell, Header, Sidebar, ConnectionStatus
      shared/         # EmptyState, StatusBadge, TestConnectionButton, etc.
    pages/            # One directory per route section (11 sections)
    theme/
      index.ts
    types/
      index.ts        # TypeScript mirrors of backend contracts
```

### Current Patterns

**Pattern 1: No existing frontend code**
- **Location:** `ui/` (absent)
- **Description:** Pure greenfield. No components, no build config, no package manager lockfile.
- **Files:** 0

**Pattern 2: FastAPI does NOT serve static files**
- **Location:** `src/lintel/api/app.py`
- **Description:** The `create_app()` factory registers 16 routers and one middleware only. No `StaticFiles` mount, no `CORSMiddleware`.
- **Files:** 1
- **Evidence:** [REPO-01]

**Pattern 3: All API routes prefixed `/api/v1`**
- **Location:** `src/lintel/api/app.py:68-81`
- **Description:** Every domain router (except `/healthz`) is under `/api/v1`. Safe for co-hosting with a static SPA: `/api/v1/*` goes to FastAPI, everything else falls through to the SPA.
- **Files:** 16 route files
- **Evidence:** [REPO-01]

**Pattern 4: No CORS configured**
- **Location:** `src/lintel/api/app.py`
- **Description:** Only `CorrelationMiddleware` is registered. Vite dev server on port 5173 will be blocked by browsers calling the FastAPI backend on port 8000.
- **Files:** 1
- **Evidence:** [REPO-01, REPO-02]

**Pattern 5: All data stores are in-memory and reset on restart**
- **Location:** `src/lintel/api/app.py:39-59` and all route files
- **Description:** Every store (repositories, credentials, skills, sandboxes, connections, settings, model policies) lives on `app.state`. Data lost on every server restart.
- **Files:** 6 route files
- **Evidence:** [REPO-01, REPO-05, REPO-06, REPO-07, REPO-08]

---

## Key Files

### Core Infrastructure

**File:** `src/lintel/api/app.py`
- **Purpose:** FastAPI app factory. Initialises projections and in-memory stores in lifespan; registers all 16 routers; adds `CorrelationMiddleware`.
- **LOC:** 86
- **Patterns:** Application factory, lifespan context manager, DI via `app.state`
- **Relevance:** HIGH -- Integration point for `StaticFiles` mount and `CORSMiddleware`.
- **Evidence:** [REPO-01]

**File:** `src/lintel/contracts/types.py`
- **Purpose:** All core domain types: `ThreadRef`, `AgentRole` (6 values), `WorkflowPhase` (8 values), `Repository`, `Credential`, `SandboxStatus` (7 values), `SkillDescriptor`, `ModelPolicy`, etc.
- **LOC:** 163
- **Patterns:** Frozen dataclasses, `StrEnum`
- **Relevance:** HIGH -- Every TypeScript type in `ui/src/types/index.ts` mirrors these. Enums drive badge colours, dropdown options, and stepper states throughout the UI.
- **Evidence:** [REPO-04]

**File:** `src/lintel/contracts/events.py`
- **Purpose:** 34 event types in `EVENT_TYPE_MAP`. All extend `EventEnvelope` (event_id, event_type, schema_version, occurred_at, actor_type, actor_id, thread_ref, correlation_id, causation_id, payload).
- **LOC:** 275
- **Patterns:** Frozen dataclasses, event registry dict
- **Relevance:** HIGH -- The Events page filter dropdown uses `GET /api/v1/events/types`. The `EventEnvelope` shape defines event detail columns.
- **Evidence:** [REPO-09]

**File:** `src/lintel/api/routes/settings.py`
- **Purpose:** Connection CRUD + test stub + general settings. Connection types: `slack`, `github`, `llm_provider`, `postgres`, `nats`.
- **LOC:** 135
- **Relevance:** HIGH -- Drives both the Settings page and the setup wizard.
- **Evidence:** [REPO-08]

**File:** `src/lintel/api/routes/agents.py`
- **Purpose:** Agent roles list, model policy CRUD per role, test-prompt stub. Defaults all 6 roles to `claude-sonnet-4-20250514`.
- **LOC:** 117
- **Relevance:** HIGH -- Drives the Agents & Models page.
- **Evidence:** [REPO-12]

**File:** `todos/2026-03-06-create-ui/index.md`
- **Purpose:** Full product specification: 11 pages, UX patterns, layout diagram, complete API dependency table (52 endpoints), planned file structure, tech stack rationale.
- **LOC:** 421
- **Relevance:** HIGH -- Canonical reference for what to build.
- **Evidence:** [REPO-17]

---

## Code Samples

### Current Pattern: FastAPI app factory -- no static files or CORS
**File:** `src/lintel/api/app.py:63-85`
```python
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Lintel", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health.router)
    app.include_router(threads.router, prefix="/api/v1")
    app.include_router(repositories.router, prefix="/api/v1")
    # ... 13 more routers under /api/v1 ...
    app.include_router(admin.router, prefix="/api/v1")
    return app
```
**Analysis:** No `CORSMiddleware` and no `StaticFiles` mount. Both are required before the UI can communicate with this backend. Must be added to this file.

### Current Pattern: In-memory state resets on restart
**File:** `src/lintel/api/app.py:39-59`
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    thread_status = ThreadStatusProjection()
    task_backlog = TaskBacklogProjection()
    engine = InMemoryProjectionEngine()
    await engine.register(thread_status)
    await engine.register(task_backlog)

    repository_store = InMemoryRepositoryStore()
    skill_store = InMemorySkillStore()
    credential_store = InMemoryCredentialStore()

    app.state.thread_status_projection = thread_status
    app.state.repository_store = repository_store
    app.state.skill_store = skill_store
    app.state.credential_store = credential_store
    yield
```
**Analysis:** Every list endpoint starts empty on each server start. The UI must show helpful empty states on every page and never assume data persists.

### Current Pattern: Domain enums driving UI badge colours and stepper
**File:** `src/lintel/contracts/types.py:42-50`
```python
class WorkflowPhase(StrEnum):
    INGESTING = "ingesting"
    PLANNING = "planning"
    AWAITING_SPEC_APPROVAL = "awaiting_spec_approval"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    AWAITING_MERGE_APPROVAL = "awaiting_merge_approval"
    MERGING = "merging"
    CLOSED = "closed"
```
**Analysis:** These 8 phases map directly to the thread detail Stepper and status badge colour scheme. TypeScript union types should mirror all StrEnums.

### Current Pattern: EventEnvelope shape
**File:** `src/lintel/contracts/events.py:17-31`
```python
@dataclass(frozen=True)
class EventEnvelope:
    event_id: UUID
    event_type: str
    schema_version: int
    occurred_at: datetime
    actor_type: ActorType
    actor_id: str
    thread_ref: ThreadRef | None
    correlation_id: UUID
    causation_id: UUID | None
    payload: dict[str, Any]
    idempotency_key: str | None
```

---

## Integration Points

### 1. Static file serving (production)
**Entry Point:** `src/lintel/api/app.py:create_app()`
**Pattern:** After all routers, mount `StaticFiles(directory="ui/dist", html=True)` and add SPA catch-all.

### 2. CORS for development
**Entry Point:** `src/lintel/api/app.py:create_app()`
**Pattern:** Add `CORSMiddleware` with `allow_origins=["http://localhost:5173"]`.

### 3. Vite dev proxy
**Entry Point:** `ui/vite.config.ts` (to be created)
**Pattern:** Proxy `/api` and `/healthz` to `http://localhost:8000`.

### 4. TypeScript types mirroring backend contracts
**Entry Point:** `ui/src/types/index.ts` (to be created)
**Pattern:** TypeScript interfaces matching all StrEnums and dataclasses from `contracts/types.py`.

### 5. Makefile frontend targets
**Entry Point:** `Makefile`
**Pattern:** Add `ui-install`, `ui-dev`, `ui-build` targets.

---

## Smells & Opportunities

1. **No CORS configuration** (XS) -- Hard blocker for UI dev
2. **No static file serving** (XS) -- Required for production
3. **No frontend entries in .gitignore** (XS) -- `node_modules/`, `ui/dist/` will be tracked
4. **No Makefile targets for frontend** (XS) -- No standard entry point for frontend devs
5. **All stores in-memory** -- Data resets on every backend restart
6. **Auto-generate TypeScript client from OpenAPI** (S) -- Eliminates manual type mirrors
7. **Dev seed script** (S) -- Eliminates re-entering test data after restarts

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Python source files | 69 |
| Total API endpoints | 52 |
| Frontend files in repo | 0 |
| `ui/` directory exists | No |
| Primary backend language | Python 3.12 |
| Domain event types | 34 |
| AgentRole enum values | 6 |
| WorkflowPhase enum values | 8 |

---

## Evidence Index

[REPO-01] `src/lintel/api/app.py:1-86` -- FastAPI app factory; all routers under `/api/v1`; no CORS, no static files
[REPO-02] `src/lintel/api/middleware/__init__.py:1-24` -- CorrelationMiddleware; propagates X-Correlation-ID header
[REPO-03] `src/lintel/api/deps.py:1-29` -- DI helpers; all state accessed via `request.app.state`
[REPO-04] `src/lintel/contracts/types.py:1-163` -- All domain types and StrEnums
[REPO-05] `src/lintel/api/routes/credentials.py:1-143` -- Credential CRUD; secrets masked on read
[REPO-06] `src/lintel/api/routes/sandboxes.py:1-91` -- Sandbox in-memory registry
[REPO-07] `src/lintel/api/routes/skills.py:1-147` -- Skill CRUD + invoke echo stub
[REPO-08] `src/lintel/api/routes/settings.py:1-135` -- Connection CRUD + test stub + general settings
[REPO-09] `src/lintel/contracts/events.py:1-275` -- 34 event types, EventEnvelope shape, EVENT_TYPE_MAP
[REPO-10] `src/lintel/api/routes/threads.py:1-19` -- GET /api/v1/threads
[REPO-11] `src/lintel/api/routes/workflows.py:1-88` -- Workflow CRUD and message processing
[REPO-12] `src/lintel/api/routes/agents.py:1-117` -- Agent roles, model policy CRUD, test-prompt stub
[REPO-13] `src/lintel/api/routes/repositories.py:1-95` -- Repository CRUD
[REPO-14] `src/lintel/api/routes/events.py:1-56` -- Event types list, events list, stream/correlation stubs
[REPO-15] `src/lintel/api/routes/metrics.py:1-64` -- PII, agent, overview metrics
[REPO-16] `src/lintel/api/routes/health.py:1-16` -- GET /healthz
[REPO-17] `todos/2026-03-06-create-ui/index.md:1-421` -- Full UI product spec
[REPO-18] `.gitignore:1-24` -- Python-only ignores; no frontend entries
[REPO-19] `Makefile:1-39` -- Python-only build targets; no frontend targets
