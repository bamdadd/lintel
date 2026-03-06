# Codebase Survey - python-api

## Survey Scope

**Tech Area:** python-api
**Task Context:** Build a React SPA web dashboard (Lintel UI) as a control plane for managing agents, workflows, connections, repositories, and observability.
**Survey Date:** 2026-03-06
**Configuration Source:** Fallback (no `docs/tech-stack/python-api.yaml` manifest found)

---

## Discovered Frameworks

| Framework | Version | Source |
|-----------|---------|--------|
| FastAPI | not pinned | imports in `src/lintel/api/` |
| Pydantic v2 | not pinned | `BaseModel` request models |
| Starlette | transitive | `BaseHTTPMiddleware` |
| structlog | not pinned | `CorrelationMiddleware` |
| LangGraph | not pinned | workflow orchestration (infra) |
| litellm | not pinned | LLM provider abstraction (infra) |
| presidio | not pinned | PII detection (infra) |

---

## Architecture Overview

### Directory Structure

```
src/lintel/
├── api/
│   ├── app.py                       # FastAPI factory + lifespan
│   ├── deps.py                      # Dependency injection helpers
│   ├── middleware/__init__.py        # CorrelationMiddleware
│   └── routes/
│       ├── health.py                # GET /healthz
│       ├── threads.py               # GET /api/v1/threads
│       ├── workflows.py             # POST/GET /api/v1/workflows[/{id}]
│       ├── agents.py                # /api/v1/agents/...
│       ├── approvals.py             # POST /api/v1/approvals/grant|reject
│       ├── repositories.py          # /api/v1/repositories[/{id}]
│       ├── sandboxes.py             # /api/v1/sandboxes[/{id}]
│       ├── skills.py                # /api/v1/skills[/{id}]
│       ├── events.py                # /api/v1/events/...
│       ├── pii.py                   # /api/v1/pii/...
│       ├── settings.py              # /api/v1/settings + /settings/connections
│       ├── workflow_definitions.py  # /api/v1/workflow-definitions[/{id}]
│       ├── metrics.py               # /api/v1/metrics/...
│       ├── credentials.py           # /api/v1/credentials[/{id}]
│       └── admin.py                 # POST /api/v1/admin/reset-projections
├── contracts/
│   ├── types.py       # Domain enums + frozen dataclasses
│   ├── commands.py    # 13 frozen command dataclasses
│   ├── events.py      # 34 event types + EVENT_TYPE_MAP
│   └── protocols.py   # Service boundary Protocol interfaces
└── infrastructure/
    ├── projections/
    │   ├── engine.py          # InMemoryProjectionEngine
    │   ├── thread_status.py   # ThreadStatusProjection
    │   └── task_backlog.py    # TaskBacklogProjection
    └── repos/
        └── repository_store.py  # InMemoryRepositoryStore
```

### Current Patterns

**Pattern 1: Router-per-domain with `/api/v1` prefix**
- **Location:** `src/lintel/api/app.py:67-81`
- **Description:** One `APIRouter` per domain, all mounted under `/api/v1` except health at root.
- **Files:** 14 route files
- **Evidence:** [REPO-01]

**Pattern 2: In-memory state via `app.state`**
- **Location:** `src/lintel/api/app.py:39-58`
- **Description:** All stores initialized in lifespan, injected via `request.app.state`. No PostgreSQL wired for most routes.
- **Evidence:** [REPO-02]

**Pattern 3: Pydantic request + `asdict()` response**
- **Location:** all route files
- **Description:** Incoming bodies are Pydantic `BaseModel`. Responses are `asdict()` of domain dataclasses -> `dict[str, Any]`. No response schemas declared on endpoints.
- **Evidence:** [REPO-03]

**Pattern 4: Commands returned but not dispatched**
- **Location:** `src/lintel/api/routes/workflows.py`, `agents.py`, `approvals.py`, `sandboxes.py`, `pii.py`
- **Description:** POST write endpoints construct frozen command dataclasses and return `asdict(command)`. No message bus dispatch -- these are stubs.
- **Evidence:** [REPO-05]

**Pattern 5: Dependency injection via `Depends()`**
- **Location:** `src/lintel/api/deps.py`
- **Description:** Projections and repo store use `Depends()` helpers. Other routes access `request.app.state` inline (inconsistent).
- **Evidence:** [REPO-04]

---

## Key Files

**File:** `/Users/bamdad/projects/lintel/src/lintel/api/app.py`
- **Purpose:** App factory, lifespan, router mounting. No CORS middleware registered.
- **LOC:** 86
- **Relevance:** HIGH

**File:** `/Users/bamdad/projects/lintel/src/lintel/api/middleware/__init__.py`
- **Purpose:** `CorrelationMiddleware` -- propagates `X-Correlation-ID` header on all requests/responses.
- **LOC:** 25
- **Relevance:** HIGH -- UI must send this header for request tracing

**File:** `/Users/bamdad/projects/lintel/src/lintel/contracts/types.py`
- **Purpose:** All core domain enums and frozen dataclasses. TypeScript types must mirror these.
- **LOC:** 163
- **Relevance:** HIGH

**File:** `/Users/bamdad/projects/lintel/src/lintel/contracts/events.py`
- **Purpose:** 34 event types + `EVENT_TYPE_MAP` registry.
- **LOC:** 275
- **Relevance:** HIGH -- used for event type filter dropdowns and event stream display

**File:** `/Users/bamdad/projects/lintel/src/lintel/api/routes/repositories.py`
- **Purpose:** Reference CRUD implementation: POST/GET/GET{id}/PATCH/DELETE, all patterns present.
- **LOC:** 95
- **Relevance:** HIGH -- canonical reference for UI fetch patterns

---

## Complete Endpoint Catalogue (56 endpoints)

### Health (1)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Liveness probe |

### Threads (1)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/threads` | List all thread statuses from projection |

### Workflows (4)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/workflows` | `{workspace_id, channel_id, thread_ts, workflow_type}` | Start workflow |
| GET | `/api/v1/workflows` | -- | List all workflows |
| GET | `/api/v1/workflows/{stream_id}` | -- | Get single workflow |
| POST | `/api/v1/workflows/messages` | `{workspace_id, channel_id, thread_ts, raw_text, sender_id, sender_name}` | Process incoming message |

### Agents (6)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/v1/agents/roles` | -- | List `AgentRole` enum values |
| GET | `/api/v1/agents/policies` | -- | Get all model policies |
| GET | `/api/v1/agents/policies/{role}` | -- | Get policy for one role |
| PUT | `/api/v1/agents/policies/{role}` | `{provider, model_name, max_tokens, temperature}` | Update policy |
| POST | `/api/v1/agents/test-prompt` | `{agent_role, messages}` | Dry-run prompt test |
| POST | `/api/v1/agents/steps` | `{workspace_id, channel_id, thread_ts, agent_role, step_name, context}` | Schedule agent step |

### Approvals (2)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/approvals/grant` | `{workspace_id, channel_id, thread_ts, gate_type, approver_id, approver_name}` | Grant gate |
| POST | `/api/v1/approvals/reject` | `{workspace_id, channel_id, thread_ts, gate_type, rejector_id, reason}` | Reject gate |

### Repositories (5)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/repositories` | `{repo_id, name, url, default_branch, owner, provider}` | Register repo |
| GET | `/api/v1/repositories` | -- | List repos |
| GET | `/api/v1/repositories/{repo_id}` | -- | Get repo |
| PATCH | `/api/v1/repositories/{repo_id}` | `{name?, default_branch?, owner?, status?}` | Partial update |
| DELETE | `/api/v1/repositories/{repo_id}` | -- | Remove repo (204) |

### Sandboxes (4)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/sandboxes` | `{workspace_id, channel_id, thread_ts, agent_role, repo_url, base_sha, commands}` | Schedule job |
| GET | `/api/v1/sandboxes` | -- | List sandbox jobs |
| GET | `/api/v1/sandboxes/{sandbox_id}` | -- | Get sandbox |
| DELETE | `/api/v1/sandboxes/{sandbox_id}` | -- | Destroy (204) |

### Skills (4)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/skills` | `{skill_id, version, name, input_schema, output_schema, execution_mode}` | Register skill |
| GET | `/api/v1/skills` | -- | List skills |
| GET | `/api/v1/skills/{skill_id}` | -- | Get skill |
| POST | `/api/v1/skills/{skill_id}/invoke` | `{input_data, context}` | Invoke skill |

### Events (4)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/events/types` | List all registered event type strings |
| GET | `/api/v1/events` | List task backlog projection events |
| GET | `/api/v1/events/stream/{stream_id}` | Get events by stream (placeholder) |
| GET | `/api/v1/events/correlation/{correlation_id}` | Get events by correlation ID (placeholder) |

### PII (3)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/pii/reveal` | `{workspace_id, channel_id, thread_ts, placeholder, requester_id, reason}` | Request PII reveal |
| GET | `/api/v1/pii/vault/log` | -- | Vault activity log |
| GET | `/api/v1/pii/stats` | -- | PII statistics |

### Settings (8)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/settings/connections` | `{connection_id, connection_type, name, config}` | Register connection |
| GET | `/api/v1/settings/connections` | -- | List connections |
| GET | `/api/v1/settings/connections/{connection_id}` | -- | Get connection |
| PATCH | `/api/v1/settings/connections/{connection_id}` | `{name?, config?}` | Update connection |
| DELETE | `/api/v1/settings/connections/{connection_id}` | -- | Delete (204) |
| POST | `/api/v1/settings/connections/{connection_id}/test` | -- | Test connection (dry-run) |
| GET | `/api/v1/settings` | -- | Get general settings |
| PATCH | `/api/v1/settings` | `{workspace_name?, default_model_provider?, pii_detection_enabled?, sandbox_enabled?, max_concurrent_workflows?}` | Update settings |

### Workflow Definitions (6)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/workflow-definitions` | `{definition_id, name, description, is_template, graph}` | Create definition |
| GET | `/api/v1/workflow-definitions` | -- | List all definitions |
| GET | `/api/v1/workflow-definitions/templates` | -- | List templates only |
| GET | `/api/v1/workflow-definitions/{definition_id}` | -- | Get definition |
| PUT | `/api/v1/workflow-definitions/{definition_id}` | `{name?, description?, graph?, is_template?}` | Update |
| DELETE | `/api/v1/workflow-definitions/{definition_id}` | -- | Delete (204) |

### Metrics (3)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/metrics/pii` | PII detection stats |
| GET | `/api/v1/metrics/agents` | Agent activity stats |
| GET | `/api/v1/metrics/overview` | Combined dashboard overview |

### Credentials (5)
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/v1/credentials` | `{credential_id, credential_type, name, secret, repo_ids}` | Store credential |
| GET | `/api/v1/credentials` | -- | List (secrets masked) |
| GET | `/api/v1/credentials/{credential_id}` | -- | Get (masked) |
| GET | `/api/v1/credentials/repo/{repo_id}` | -- | List for repo |
| DELETE | `/api/v1/credentials/{credential_id}` | -- | Revoke (204) |

### Admin (1)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/admin/reset-projections` | Reset all in-memory projections |

---

## TypeScript Types to Mirror

```typescript
// From src/lintel/contracts/types.py

type ActorType = 'human' | 'agent' | 'system';
type AgentRole = 'planner' | 'coder' | 'reviewer' | 'pm' | 'designer' | 'summarizer';
type WorkflowPhase = 'ingesting' | 'planning' | 'awaiting_spec_approval' | 'implementing' | 'reviewing' | 'awaiting_merge_approval' | 'merging' | 'closed';
type RepoStatus = 'active' | 'archived' | 'error';
type CredentialType = 'ssh_key' | 'github_token';
type SandboxStatus = 'pending' | 'creating' | 'running' | 'collecting' | 'completed' | 'failed' | 'destroyed';
type SkillExecutionMode = 'inline' | 'async_job' | 'sandbox';

interface ThreadRef { workspace_id: string; channel_id: string; thread_ts: string; }
interface Repository { repo_id: string; name: string; url: string; default_branch: string; owner: string; provider: string; status: RepoStatus; }
interface Credential { credential_id: string; credential_type: CredentialType; name: string; repo_ids: string[]; secret_preview?: string; }
interface ModelPolicy { provider: string; model_name: string; max_tokens: number; temperature: number; }
interface SkillDescriptor { skill_id: string; name: string; version: string; description: string; input_schema: Record<string, unknown> | null; output_schema: Record<string, unknown> | null; execution_mode: SkillExecutionMode; allowed_agent_roles: string[]; }
interface SandboxRecord { sandbox_id: string; status: SandboxStatus; repo_url: string; base_sha: string; commands: string[]; agent_role: AgentRole; thread_ref: ThreadRef; created_at: string; }
interface Connection { connection_id: string; connection_type: string; name: string; config: Record<string, unknown>; status: string; }
interface GeneralSettings { workspace_name: string; default_model_provider: string; pii_detection_enabled: boolean; sandbox_enabled: boolean; max_concurrent_workflows: number; }
interface WorkflowDefinitionGraph { nodes: string[]; edges: [string, string][]; conditional_edges: Array<{ source: string; targets: Record<string, string> }>; entry_point: string; interrupt_before: string[]; }
interface WorkflowDefinition { definition_id: string; name: string; description: string; is_template: boolean; graph: WorkflowDefinitionGraph; created_at: string; updated_at: string; }
interface EventEnvelope { event_id: string; event_type: string; schema_version: number; occurred_at: string; actor_type: ActorType; actor_id: string; thread_ref: ThreadRef | null; correlation_id: string; causation_id: string | null; payload: Record<string, unknown>; idempotency_key: string | null; }
interface PIIStats { total_scanned: number; total_detected: number; total_anonymised: number; total_blocked: number; total_reveals: number; }
interface OverviewMetrics { pii: PIIStats; sandboxes: { total: number }; connections: { total: number }; }
```

---

## Integration Points

**1. Dashboard overview:** `GET /api/v1/metrics/overview` -- single call, returns pii/sandboxes/connections counts

**2. Workflow list/detail:** `GET /api/v1/workflows` and `GET /api/v1/workflows/{stream_id}` -- `stream_id` format is `thread:{workspace_id}:{channel_id}:{thread_ts}`

**3. Approval actions:** `POST /api/v1/approvals/grant` and `/reject` -- triggered from workflow detail UI when workflow is in `awaiting_spec_approval` or `awaiting_merge_approval` phase

**4. Repository CRUD:** Standard REST at `/api/v1/repositories`

**5. Agent policy config:** `GET/PUT /api/v1/agents/policies/{role}` -- role must match `AgentRole` enum

**6. Event stream viewer:** `GET /api/v1/events/types` for filter dropdown, `GET /api/v1/events` for backlog; stream/correlation endpoints are placeholders

---

## Critical Findings for UI Development

### Authentication: None
No auth is implemented. The API is fully open. Design the UI ready for auth but no credentials are needed now.

### CORS: Not configured
`src/lintel/api/app.py` adds only `CorrelationMiddleware`. No `CORSMiddleware`. Browser fetch calls will be blocked by CORS unless:
- A Vite dev proxy is configured, OR
- `fastapi.middleware.cors.CORSMiddleware` is added to `app.py`

This is an XS fix on the backend but blocks all UI development without it.

### OpenAPI spec available
FastAPI auto-generates OpenAPI at `/docs` (Swagger UI) and `/openapi.json`. Once response models are added, `openapi-typescript` can auto-generate TypeScript types.

### All write endpoints are stubs
POST/PUT/PATCH/DELETE calls succeed and return valid-shaped data, but no real side effect occurs. The in-memory state updates but resets on restart. UI should handle empty states gracefully.

### `X-Correlation-ID` header
The UI should send `X-Correlation-ID: <uuid>` on all requests. The middleware echoes it back in the response. [REPO-06]

---

## Smells & Opportunities

1. **No CORS middleware** (Complexity: XS) -- Add `CORSMiddleware` in `app.py:65`. Unblocks all browser-based UI calls immediately.
2. **No response schemas** (Complexity: M) -- Add Pydantic response models to all endpoints. Enables OpenAPI code generation for TypeScript.
3. **All storage is volatile** (Complexity: L) -- In-memory stores reset on restart. PostgreSQL event store exists in infra but is not wired to most routes.
4. **Inconsistent `app.state` access** (Complexity: S) -- 6 route files bypass `deps.py` and read `app.state` directly. Standardize to `Depends()`.
5. **`frozenset` serialization** (Complexity: XS) -- `Credential.repo_ids` and `SkillDescriptor.allowed_agent_roles` are `frozenset`; `asdict()` produces lists. TypeScript should always treat these as arrays.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Route Files | 14 |
| Total Endpoints | 56 |
| Primary Language | Python 3.12+ |
| Event Types | 34 |
| Command Types | 13 |
| Authentication | None |
| CORS | Not configured |
| Response Models | None (all `dict[str,Any]`) |
| Persistence | In-memory only |

---

## Evidence Index

[REPO-01] `/Users/bamdad/projects/lintel/src/lintel/api/app.py:63-85` -- App factory, all routers, no CORS
[REPO-02] `/Users/bamdad/projects/lintel/src/lintel/api/app.py:39-58` -- Lifespan, in-memory store init
[REPO-03] `/Users/bamdad/projects/lintel/src/lintel/api/routes/workflows.py:33-47` -- `dict[str,Any]` response pattern
[REPO-04] `/Users/bamdad/projects/lintel/src/lintel/api/deps.py:1-28` -- `Depends()` helpers
[REPO-05] `/Users/bamdad/projects/lintel/src/lintel/contracts/commands.py:1-116` -- Command dataclasses (stub dispatch)
[REPO-06] `/Users/bamdad/projects/lintel/src/lintel/api/middleware/__init__.py:16-24` -- `X-Correlation-ID` middleware
[REPO-07] `/Users/bamdad/projects/lintel/src/lintel/contracts/types.py:1-163` -- All domain enums and dataclasses
[REPO-08] `/Users/bamdad/projects/lintel/src/lintel/contracts/events.py:1-275` -- 34 event types + registry
[REPO-09] `/Users/bamdad/projects/lintel/src/lintel/api/routes/repositories.py:1-95` -- Reference CRUD implementation
[REPO-10] `/Users/bamdad/projects/lintel/src/lintel/api/routes/settings.py:1-135` -- Connections + general settings
[REPO-11] `/Users/bamdad/projects/lintel/src/lintel/api/routes/metrics.py:43-63` -- Overview metrics
[REPO-12] `/Users/bamdad/projects/lintel/src/lintel/api/routes/workflows.py:50-88` -- Workflow list/detail/message
[REPO-13] `/Users/bamdad/projects/lintel/src/lintel/api/routes/approvals.py:33-64` -- Grant/reject approvals
[REPO-14] `/Users/bamdad/projects/lintel/src/lintel/api/routes/agents.py:52-83` -- Model policy endpoints
[REPO-15] `/Users/bamdad/projects/lintel/src/lintel/api/routes/events.py:14-55` -- Event query endpoints
