# Create a UI - Research

**EXECUTIVE SUMMARY**

Lintel's backend is API-complete: 56 endpoints across 14 route files, all returning stub data from in-memory stores. The domain contracts (`types.py`, `events.py`) are well-structured frozen dataclasses that map cleanly to TypeScript. However, two blockers must be resolved before any UI work: (1) no CORS middleware and (2) no typed response models (all endpoints return `dict[str, Any]`, making OpenAPI-based TypeScript client generation useless).

The frontend is pure greenfield -- no `ui/` directory, no Node.js tooling, no `.gitignore` entries for frontend artifacts. The planned tech stack (React 18 + Mantine v7 + TanStack Query v5 + React Flow + Vite) is well-supported by current best practices and framework documentation.

- **Recommended Approach**: Option A -- Orval-Generated TypeScript Client with Feature-Based SPA
- **Why**: Eliminates manual type maintenance for 56 endpoints; Orval generates TanStack Query hooks per tag group; feature-based folders scale to 11+ page sections
- **Trade-offs**: Requires adding Pydantic response models to all endpoints first (M effort on backend)
- **Confidence**: High -- all frameworks are production-proven; the API surface is well-defined
- **Next Step**: User decision required -- review options below

---

## 1. Problem Statement

- **Original Task**: Build a React SPA web dashboard serving as the control plane for Lintel -- managing agents, workflows, connections, repositories, and observability
- **Success Criteria**: 11 page sections functional; setup wizard for first-run onboarding; real-time event feed; visual workflow editor; dark mode; `Cmd+K` command palette
- **Key Questions**: How to integrate with the existing FastAPI backend? Hand-write or auto-generate the TypeScript API client? How to structure a 10+ page SPA for maintainability?
- **Assumptions to Validate**: The 56 API endpoints are sufficient for all UI features; Mantine v7 covers the needed components; React Flow can handle the workflow editor requirements

## 2. Investigation Summary

- **Codebase survey (python-api)**: Analyzed 14 route files, 56 endpoints, all domain contracts. Found: no CORS, no response models, all stores in-memory.
- **Codebase survey (react-ui)**: Confirmed pure greenfield -- no `ui/` directory, no frontend code, no Node tooling.
- **Framework documentation**: Reviewed Mantine v7 (AppShell, Stepper, forms, charts, notifications, dark mode), TanStack Query v5 (polling, mutations, cache), React Flow (custom nodes, drag-and-drop), React Router v7 (nested layouts), Vite (proxy, build), FastAPI (StaticFiles, CORS, SSE, OpenAPI), Pydantic v2 (response models, serializers).
- **Web research**: Surveyed 2025-2026 best practices for admin dashboards, FastAPI+React integration, TypeScript client generation (Orval, @hey-api/openapi-ts), SSE streaming.
- **Clean code analysis**: Identified 10 issues on the backend (response types, CORS, auth, DRY violations) and 11 patterns to establish for the frontend (feature folders, branded types, query key factories, error boundaries).

**Evidence collected**: 19 repo files, 30+ framework doc references, 18 web sources, 17 clean code findings.

## 3. Key Findings

### Finding 1: All 56 Endpoints Return Untyped Dicts
- **Discovery**: Every route handler returns `dict[str, Any]` or `list[dict[str, Any]]`. The OpenAPI schema has empty object types for all responses.
- **Evidence**: [CLEAN-01, REPO-03]
- **Implication**: TypeScript client generation (Orval, openapi-typescript) produces `Record<string, unknown>` -- useless. Either add Pydantic response models (Option A) or hand-write TypeScript types (Option B/C).

### Finding 2: No CORS Middleware -- Hard Blocker
- **Discovery**: `app.py` adds only `CorrelationMiddleware`. Any browser request from a different origin (Vite dev server) is blocked.
- **Evidence**: [CLEAN-04, REPO-01]
- **Implication**: Must add `CORSMiddleware` or use Vite proxy. Both are XS effort.

### Finding 3: Domain Contracts Are Clean and Complete
- **Discovery**: `contracts/types.py` defines 7 `StrEnum` types and 8 frozen dataclasses. `contracts/events.py` defines 34 event types with a complete registry. These map 1:1 to TypeScript union types and interfaces.
- **Evidence**: [REPO-07, REPO-08]
- **Implication**: TypeScript type mirroring is mechanical -- can be auto-generated from OpenAPI if response models are added.

### Finding 4: In-Memory Stores Reset on Every Restart
- **Discovery**: All data stores live on `app.state` and are initialized fresh in the lifespan handler. No persistence.
- **Evidence**: [REPO-02]
- **Implication**: UI must handle empty states on every page. A dev seed script or MSW mocking is needed for productive frontend iteration.

### Finding 5: Mantine v7 Covers ~80% of UI Components
- **Discovery**: Mantine v7 provides AppShell (layout), Stepper (wizard + phase indicator), Timeline (event history), Spotlight (Cmd+K), Charts (PII dashboard), notifications (async feedback), forms (validation), and dark mode -- all out of the box.
- **Evidence**: [MANTINE-01 through MANTINE-10]
- **Implication**: Minimal custom component development needed. Focus effort on the React Flow workflow editor and data integration.

### Finding 6: Orval Generates Complete TanStack Query Hooks from OpenAPI
- **Discovery**: Orval in `react-query` + `tags-split` mode generates one typed hook file per endpoint tag -- `useQuery` for reads, `useMutation` for writes, with cache invalidation. Zero manual hook writing for 56 endpoints.
- **Evidence**: [WEB-06 python-api, DOCS-16]
- **Implication**: If Pydantic response models are added, the entire API client layer is auto-generated with full type safety.

### Finding 7: FastAPI Has Native SSE Support
- **Discovery**: FastAPI 0.135.0 added `EventSourceResponse` and `ServerSentEvent` with built-in keep-alive, `Cache-Control: no-cache`, and `X-Accel-Buffering: no`.
- **Evidence**: [WEB-08 python-api, DOCS-4]
- **Implication**: Real-time event streaming for the dashboard feed and thread detail is straightforward. TanStack Query polling is the simpler alternative for MVP.

## 4. Analysis & Synthesis

### Current State
The backend API surface is complete but unpolished for web client consumption. All 56 endpoints work and return valid-shaped data, but without typed response models the OpenAPI contract is meaningless for code generation. The domain layer (`contracts/`) is exemplary -- clean frozen dataclasses with `StrEnum` constants that map directly to TypeScript. The architecture boundary between contracts and infrastructure is well-maintained.

### Constraints & Opportunities
**Constraints:**
- No frontend code exists -- everything must be scaffolded from scratch
- All backend stores are in-memory -- UI development requires either a seed script or mock layer
- Package manager must be **bun** (user preference)
- Uncommitted backend changes add new route files (agents, approvals, credentials, events, metrics, pii, sandboxes, settings, skills, workflow_definitions, workflows, admin)

**Opportunities:**
- FastAPI's `/openapi.json` can drive automatic TypeScript client generation via Orval
- Mantine v7 provides most UI components needed out of the box
- Feature-based folder structure can be established from day one (zero migration cost)
- Vite dev proxy eliminates CORS issues during development

### Design Principles
- **Single source of truth for types**: Pydantic models -> OpenAPI -> TypeScript (no hand-written type mirrors)
- **Feature-based organization**: One folder per domain (threads, agents, workflows, etc.) with co-located components, hooks, and API functions
- **Server state in TanStack Query only**: No duplicating API data in `useState`
- **URL state for shareable views**: Filters, pagination, and active tabs in `useSearchParams`
- **Empty states everywhere**: Every list view must gracefully handle zero data

## 5. Solution Space

### Option A: Orval-Generated Client + Feature-Based SPA
**Core Idea**: Add Pydantic response models to all FastAPI endpoints, then use Orval to auto-generate typed TanStack Query hooks. Build the SPA with feature-based folders.

**Approach Overview**:
- Backend prep: Add ~25 Pydantic response models, add CORS, add `generate_unique_id_function`
- Frontend scaffold: Vite + React 18 + TypeScript with bun
- API layer: Orval generates `useQuery`/`useMutation` hooks per endpoint tag
- Structure: `features/` per domain, `shared/` for cross-cutting, `app/` for routing

**Key Trade-offs**:
- Pros:
  - Zero manual API hook writing for 56 endpoints [WEB-06 python-api]
  - Types stay in sync automatically -- change Python model, re-run Orval [DOCS-16]
  - Feature-based folders scale to 11+ page sections [WEB-16]
  - Mantine covers most UI needs out of the box [MANTINE-01 through MANTINE-10]
- Cons:
  - Requires M-effort backend work first (Pydantic response models) [CLEAN-01]
  - Orval adds a build step and dependency
  - Generated code may need customization for complex transforms (snake_case -> camelCase)

**Complexity**: M (backend prep) + L (frontend build)
**Best When**: Team values type safety and has capacity for backend model work upfront

### Option B: Hand-Written TypeScript Client + Feature-Based SPA
**Core Idea**: Skip backend response model changes. Hand-write TypeScript types mirroring `contracts/types.py` and a thin `apiClient` wrapper. Build the SPA with the same feature-based structure.

**Approach Overview**:
- No backend changes needed beyond CORS
- Hand-write `ui/src/types/index.ts` mirroring all domain types
- Hand-write `apiClient` with fetch wrapper + per-feature query hooks
- Same feature-based folder structure

**Key Trade-offs**:
- Pros:
  - No backend work needed -- start building UI immediately
  - Full control over API client shape and transforms
  - No Orval dependency or build step
- Cons:
  - Manual type maintenance across 56 endpoints (drift risk) [CLEAN-01]
  - Must hand-write every `useQuery`/`useMutation` hook
  - No server-side response validation (backend returns `dict[str, Any]`)
  - OpenAPI spec remains unusable for documentation

**Complexity**: S (backend) + L (frontend build, higher ongoing maintenance)
**Best When**: Team wants to start UI work immediately without backend changes

### Option C: Hybrid -- Hand-Written Types Now, Orval Later
**Core Idea**: Start with hand-written TypeScript types and API client for immediate progress. Add Pydantic response models incrementally. Switch to Orval when models are complete.

**Approach Overview**:
- Phase 1: Hand-write types, add CORS, scaffold SPA, build first pages
- Phase 2: Add Pydantic response models to highest-traffic endpoints
- Phase 3: Switch to Orval when >80% of endpoints have response models

**Key Trade-offs**:
- Pros:
  - Immediate UI development -- no backend blocking
  - Incremental backend improvement
  - Orval migration can happen when convenient
- Cons:
  - Two type systems during transition (hand-written + generated)
  - Must maintain hand-written types until Orval switch
  - Migration effort is non-zero

**Complexity**: S (start) + M (transition) + L (frontend build)
**Best When**: UI development is time-sensitive; backend model work can be phased

## 6. Recommendation

**Recommended Approach**: Option A -- Orval-Generated Client + Feature-Based SPA

**Why This Option Wins**:
- With 56 endpoints, hand-writing and maintaining typed hooks is error-prone and tedious. Orval eliminates this entire class of work. [WEB-06 python-api]
- The domain dataclasses in `contracts/types.py` are already well-defined -- mirroring them as Pydantic response models is mechanical. [REPO-07]
- The type chain (Pydantic -> OpenAPI -> Orval -> TypeScript) provides end-to-end type safety with a single source of truth. [DOCS-16]

**Trade-offs Accepted**:
- M-effort backend work (Pydantic response models) must happen before Orval can generate useful types
- Orval adds a build step (`bunx orval` in pre-commit or CI)

**Key Risks**:
- Pydantic response models take longer than expected -- Mitigation: start with highest-priority endpoints (threads, workflows, settings) and iterate
- Orval-generated code doesn't handle snake_case transform -- Mitigation: configure Orval's `transformer` option or add a thin wrapper
- In-memory stores frustrate UI testing -- Mitigation: MSW mock layer for frontend-only development

See [risks.md](./research/risks.md) for detailed risk analysis.

**Confidence**: High
- Rationale: All frameworks are production-proven. The API surface is complete. The domain model is well-structured. The only uncertainty is the effort for Pydantic response models, which is bounded.

## 7. Next Steps

**Decision Required**:
Review the solution options above and select the approach that best fits project constraints and priorities.

**Questions to Consider**:
- Is the M-effort for Pydantic response models acceptable before starting UI work?
- Should we use bun (confirmed by user) for package management?
- Do we want MSW for frontend-only development, or always run the real backend?

**Once Direction is Chosen**:
Proceed to `/plan` for detailed implementation planning.

The plan phase will provide:
- Architecture diagrams and component boundaries
- Sequenced implementation steps with file-level detail
- Complete code examples and configurations
- Testing strategy and validation criteria
- Phased implementation checklist

---

## APPENDICES

*Detailed context for plan agent and technical deep-dive*

### Codebase Survey - python-api
**Purpose**: Complete backend API surface for UI integration

**Summary**: 56 endpoints across 14 route files. All return `dict[str, Any]`. Domain contracts (7 StrEnums, 8 dataclasses, 34 event types) are clean. No CORS, no auth, all stores in-memory.

**Key Findings**:
- 56 endpoints mapped with request/response shapes
- TypeScript type equivalents derived from domain dataclasses
- `X-Correlation-ID` middleware must be propagated by UI
- `stream_id` format: `thread:{workspace_id}:{channel_id}:{thread_ts}`

**Contents** ([full details](./research/codebase-survey-python-api.md)):
- Architecture overview and patterns
- Complete endpoint catalogue with request bodies
- TypeScript types to mirror
- Integration points and critical findings

---

### Codebase Survey - react-ui
**Purpose**: Assess existing frontend infrastructure

**Summary**: Pure greenfield. No `ui/` directory, no frontend code, no Node tooling, no `.gitignore` entries for frontend artifacts. The product spec in `index.md` is comprehensive.

**Key Findings**:
- Zero frontend files exist
- FastAPI has no StaticFiles mount or CORS
- `.gitignore` and `Makefile` need frontend entries
- Product spec defines 11 pages, complete API map, and file structure

**Contents** ([full details](./research/codebase-survey-react-ui.md)):
- Planned UI structure from index.md
- Integration points (CORS, StaticFiles, Vite proxy)
- Opportunities (OpenAPI client gen, dev seed script)

---

### Framework Docs - python-api
**Purpose**: FastAPI patterns for serving SPAs, CORS, SSE, OpenAPI

**Summary**: FastAPI supports all needed patterns: StaticFiles + SPA catch-all, CORSMiddleware, native SSE (0.135.0+), `generate_unique_id_function` for clean OpenAPI operation IDs, Pydantic v2 `from_attributes` for dataclass conversion.

**Key Findings**:
- SPA catch-all must be registered AFTER API routers
- Native SSE with built-in keep-alive and proxy headers
- `generate_unique_id_function` controls TypeScript function names
- `ConfigDict(from_attributes=True)` converts frozen dataclasses

**Contents** ([full details](./research/framework-docs-python-api.md)):
- StaticFiles, CORS, SSE, WebSocket patterns
- Pydantic v2 response models and serializers
- Anti-patterns to avoid

---

### Framework Docs - react-ui
**Purpose**: Framework APIs and best practices for the UI stack

**Summary**: Mantine v7 covers ~80% of needed components. TanStack Query v5 has breaking changes from v4. React Flow requires module-level nodeTypes. React Router v7 uses `createBrowserRouter`. Vite proxy eliminates CORS in dev.

**Key Findings**:
- Mantine AppShell compound components, Stepper, forms, notifications, charts, Spotlight
- TanStack Query: `refetchInterval` function for conditional polling; v5 API changes
- React Flow: custom nodes, drag-and-drop, module-level nodeTypes mandatory
- Vite: proxy config, production build, manual chunks

**Contents** ([full details](./research/framework-docs-react-ui.md)):
- Code examples for all major patterns
- Anti-patterns and migration considerations

---

### Web Research - react-ui
**Purpose**: Current best practices for React admin dashboards (2025-2026)

**Summary**: Feature-based folder structure is consensus. Mantine AppShell + Spotlight covers layout + command palette. TanStack Query conditional polling for real-time data. React Flow + Zustand + dagre.js for workflow editor.

**Key Findings**:
- `@mantine/spotlight` for Cmd+K command palette
- `refetchInterval: (query) => condition ? ms : false` for adaptive polling
- React Flow nodeTypes at module scope (performance-critical)
- Vite proxy eliminates CORS; `lazy:` route option for code splitting

**Contents** ([full details](./research/web-research-react-ui.md)):
- 7 topics researched with confidence ratings
- Production learnings from reference projects

---

### Web Research - python-api
**Purpose**: FastAPI + React integration, TypeScript client generation, SSE

**Summary**: Orval in `react-query` + `tags-split` mode is recommended for 56 endpoints. Native FastAPI SSE (0.135.0+) for event streaming. Single-container Docker deployment. Commit `openapi.json` and regenerate client in CI.

**Key Findings**:
- Orval generates TanStack Query hooks per endpoint tag
- FastAPI native SSE with built-in proxy-friendly headers
- `generate_unique_id_function` essential for clean client names
- Pre-commit hook: export OpenAPI -> run Orval -> commit generated client

**Contents** ([full details](./research/web-research-python-api.md)):
- 7 topics researched with confidence ratings
- CI/CD workflow for TypeScript client generation

---

### Clean Code - react-ui
**Purpose**: React/TypeScript patterns for the greenfield UI

**Summary**: 11 patterns to establish from day one: feature-based folders, branded types, query key factories, container/presentational separation, API client abstraction, URL state for filters, error boundaries, snake_case transforms, Zod validation, RTL+MSW testing, accessibility.

**Key Findings**:
- Mirror Python's `NewType` with TypeScript branded types
- TanStack Query key factories prevent stale cache bugs
- `apiClient` abstraction propagates `X-Correlation-ID`
- State ownership: TanStack Query (server), useSearchParams (URL), useState (ephemeral)

**Contents** ([full details](./research/clean-code-react-ui.md)):
- 11 improvements with code examples and priority
- Anti-pattern checklist

---

### Clean Code - python-api
**Purpose**: API code quality for UI integration readiness

**Summary**: 10 issues found. Top 3 blockers: no typed response models (40 endpoints), no CORS, no auth. Medium issues: placeholder 200 responses, verb-in-path routes, duplicate endpoints, inconsistent DI.

**Key Findings**:
- All 40 endpoints return `dict[str, Any]` -- blocks TypeScript codegen
- No CORS -- blocks all browser requests
- `GET /threads` and `GET /workflows` return identical data
- 7 lazy `hasattr` init functions scattered across route files

**Contents** ([full details](./research/clean-code-python-api.md)):
- 10 violations with file locations and proposed fixes
- Metrics and anti-pattern checklist

---

### Evidence Index
**Purpose**: Complete citation trail

**Summary**: 19 repo evidence items, 30+ framework doc references, 18 web research sources, 17 clean code findings.

**Contents** ([full details](./research/evidence-index.md)):
- REPO-XX: Repository evidence
- DOCS-XX / MANTINE-XX / TANSTACK-XX / REACTFLOW-XX / ROUTER-XX / VITE-XX: Framework docs
- CLEAN-XX: Clean code analysis
- WEB-XX: Web research

---

### Risks & Troubleshooting
**Purpose**: Anticipate issues for plan phase

**Summary**: 8 risks identified. Top 3: no CORS (certain, high impact, XS fix), no typed response models (certain, high impact, M fix), in-memory stores (certain, medium impact). 6 common issues documented with solutions.

**Risk Profile**:
- High impact: CORS blocker (XS fix), untyped responses (M fix)
- Medium impact: in-memory stores, React Flow nodeTypes, Mantine CSS imports
- Low impact: TanStack Query v5 API drift, HTTP/1.1 SSE limit

**Contents** ([full details](./research/risks.md)):
- 8 risks with likelihood/impact/mitigation
- 6 common issues and solutions
- Testing considerations
