# Evidence Index

Consolidated evidence from all research agents across react-ui and python-api tech areas.

---

## Repository Evidence (REPO-XX)

| ID | File/Location | Finding | Confidence |
|----|---------------|---------|------------|
| REPO-01 | `src/lintel/api/app.py:63-85` | App factory: 16 routers under `/api/v1`, no CORS, no StaticFiles | 0.95 |
| REPO-02 | `src/lintel/api/app.py:39-58` | Lifespan: all stores in-memory, reset on restart | 0.95 |
| REPO-03 | `src/lintel/api/routes/workflows.py:33-47` | `dict[str, Any]` response pattern -- no typed response models | 0.95 |
| REPO-04 | `src/lintel/api/deps.py:1-28` | `Depends()` helpers for projections/repo store only | 0.90 |
| REPO-05 | `src/lintel/contracts/commands.py:1-116` | 13 frozen command dataclasses (stub dispatch) | 0.95 |
| REPO-06 | `src/lintel/api/middleware/__init__.py:16-24` | `X-Correlation-ID` middleware | 0.95 |
| REPO-07 | `src/lintel/contracts/types.py:1-163` | All domain enums (7 StrEnums) and frozen dataclasses | 0.95 |
| REPO-08 | `src/lintel/contracts/events.py:1-275` | 34 event types + EVENT_TYPE_MAP registry | 0.95 |
| REPO-09 | `src/lintel/api/routes/repositories.py:1-95` | Reference CRUD implementation | 0.90 |
| REPO-10 | `src/lintel/api/routes/settings.py:1-135` | Connections + general settings (5 connection types) | 0.90 |
| REPO-11 | `src/lintel/api/routes/metrics.py:43-63` | Overview metrics endpoint | 0.90 |
| REPO-12 | `src/lintel/api/routes/workflows.py:50-88` | Workflow list/detail/message endpoints | 0.90 |
| REPO-13 | `src/lintel/api/routes/approvals.py:33-64` | Grant/reject approvals (verb-in-path) | 0.90 |
| REPO-14 | `src/lintel/api/routes/agents.py:52-83` | Model policy CRUD, all 6 roles default to claude-sonnet | 0.90 |
| REPO-15 | `src/lintel/api/routes/events.py:14-55` | Event query endpoints (stream/correlation are stubs) | 0.90 |
| REPO-16 | `src/lintel/api/routes/health.py:1-16` | GET /healthz returns `{"status": "ok"}` | 0.95 |
| REPO-17 | `todos/2026-03-06-create-ui/index.md:1-421` | Full UI product spec | 0.95 |
| REPO-18 | `.gitignore:1-24` | Python-only ignores; no frontend entries | 0.95 |
| REPO-19 | `Makefile:1-39` | Python-only build targets; no frontend targets | 0.95 |

## Framework Documentation Evidence (DOCS-XX)

| ID | Source | Topic | Framework | Confidence |
|----|--------|-------|-----------|------------|
| DOCS-1 | FastAPI/Starlette | StaticFiles + SPA catch-all | FastAPI | 0.95 |
| DOCS-2 | FastAPI | CORSMiddleware configuration | FastAPI | 0.95 |
| DOCS-3 | FastAPI | generate_unique_id_function for OpenAPI | FastAPI | 0.95 |
| DOCS-4 | FastAPI | StreamingResponse / SSE | FastAPI | 0.93 |
| DOCS-5 | FastAPI | WebSocket endpoints | FastAPI | 0.90 |
| DOCS-6 | FastAPI | Response Model / response_model_exclude_none | FastAPI | 0.92 |
| DOCS-10 | Pydantic v2 | ConfigDict / from_attributes | Pydantic | 0.95 |
| DOCS-12 | Pydantic v2 | @field_serializer for frozenset/UUID | Pydantic | 0.93 |
| DOCS-13 | Pydantic v2 | Discriminated Unions | Pydantic | 0.90 |
| DOCS-16 | FastAPI + openapi-typescript | TypeScript client generation | FastAPI | 0.92 |
| DOCS-17 | FastAPI/Starlette | SPA production layout | FastAPI | 0.92 |
| MANTINE-01 | Mantine v7 | AppShell compound components | Mantine | 0.95 |
| MANTINE-02 | Mantine v7 | Stepper multi-step form | Mantine | 0.92 |
| MANTINE-03 | Mantine v7 | useForm + zodResolver | Mantine | 0.92 |
| MANTINE-04 | Mantine v7 | Notifications loading transitions | Mantine | 0.92 |
| MANTINE-05 | Mantine v7 | Dark mode / ColorSchemeScript | Mantine | 0.95 |
| MANTINE-06 | Mantine v7 | @mantine/charts | Mantine | 0.90 |
| MANTINE-10 | Mantine v7 | @mantine/spotlight command palette | Mantine | 0.87 |
| TANSTACK-01 | TanStack Query v5 | QueryClient setup | TanStack | 0.93 |
| TANSTACK-03 | TanStack Query v5 | refetchInterval conditional polling | TanStack | 0.93 |
| TANSTACK-05 | TanStack Query v5 | Query key factory | TanStack | 0.92 |
| REACTFLOW-01 | React Flow v11 | Canvas setup, nodeTypes | React Flow | 0.90 |
| REACTFLOW-03 | React Flow v11 | Drag-and-drop from palette | React Flow | 0.90 |
| ROUTER-01 | React Router v7 | createBrowserRouter nested layouts | React Router | 0.92 |
| VITE-02 | Vite v5 | server.proxy for FastAPI dev | Vite | 0.95 |

## Clean Code Analysis Evidence (CLEAN-XX)

| ID | Issue Type | Location | Severity | Confidence |
|----|-----------|----------|----------|------------|
| CLEAN-01 | Type Safety | All 40 endpoints return `dict[str, Any]` | High | 0.95 |
| CLEAN-02 | Type Safety | Workflows: untyped dict responses | High | 0.95 |
| CLEAN-03 | Type Safety | Agents: untyped dict responses | High | 0.95 |
| CLEAN-04 | Security/CORS | No CORSMiddleware in app.py | High | 0.95 |
| CLEAN-05 | Security | No authentication scheme | High | 0.90 |
| CLEAN-06 | Security | Admin endpoint unprotected | High | 0.90 |
| CLEAN-07 | Error Handling | Placeholder 200 on event endpoints | Medium | 0.90 |
| CLEAN-08 | REST Convention | Verb-in-path: /approvals/grant | Medium | 0.85 |
| CLEAN-10 | DRY | Duplicate /threads and /workflows list | Medium | 0.90 |
| CLEAN-14 | SRP | InMemoryCredentialStore in route file | Medium | 0.85 |
| CLEAN-17 | DRY | ThreadRef fields repeated across 8 handlers | Medium | 0.85 |

## Web Research Evidence (WEB-XX)

| ID | Topic | Source | Confidence |
|----|-------|--------|------------|
| WEB-01 | Mantine AppShell | Mantine Changelog v7.0.0 | 0.95 |
| WEB-03 | Mantine Forms + Stepper | Mantine Docs | 0.92 |
| WEB-05 | TanStack Query Polling | TanStack Docs | 0.93 |
| WEB-06 | TanStack Optimistic Updates | TanStack Docs | 0.93 |
| WEB-08 | React Flow + Zustand | Synergy Codes | 0.88 |
| WEB-10 | Vite FastAPI Proxy | Josh Finnie | 0.95 |
| WEB-11 | Vite FastAPI Production | TestDriven.io | 0.92 |
| WEB-12 | RR v7 Protected Routes | DEV Community | 0.90 |
| WEB-16 | SPA Folder Structure | Medium | 0.90 |
