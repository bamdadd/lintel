# Clean Code Analysis - react-ui

## Analysis Scope

**Tech Area:** react-ui
**Task Context:** Build a React SPA web dashboard using React 18 + TypeScript, Mantine v7, TanStack Query v5, React Flow, and Vite.
**Analysis Date:** 2026-03-06
**Clean Code Docs:** Built-in principles (no `docs/clean-code/react-ui/` found in repository)

---

## Python Codebase Style Patterns (to mirror in the UI)

1. **Frozen dataclasses as value objects** -- maps to TypeScript `readonly` interfaces and `as const` enum-like objects
2. **Protocol-based dependency inversion** -- maps to TypeScript interfaces for service/repository boundaries
3. **Feature-grouped modules** -- `contracts/`, `domain/`, `api/routes/` map to feature-based folder structure in the SPA
4. **`NewType` for semantic IDs** -- mirror with branded types in TypeScript
5. **Past-tense event names** -- `WorkflowStarted`, `AgentStepCompleted` are semantically clear; use the same naming in frontend event-type enums
6. **`StrEnum` for domain constants** -- mirror with `const` object + `typeof` unions in TypeScript
7. **Short, single-purpose route files** -- each route file is under 90 lines. Mirror by keeping each feature's API hook file focused
8. **Annotated Pydantic request models per endpoint** -- mirror with dedicated Zod schemas per form/mutation

---

## Violations & Improvements

### 1. Missing Feature-Based Folder Structure (Greenfield Risk)

**Principle Violated:** Single Responsibility Principle / Separation of Concerns

**Proposed Structure:**
```
src/
  features/
    threads/
      components/          # ThreadTable, ThreadStatusBadge
      hooks/               # useThreads, useThreadDetail
      api/                 # threadsQueryKeys, threadsApi
      types.ts             # ThreadStatus, ThreadSummary
      index.ts             # public API barrel export
    workflows/
    agents/
    credentials/
    sandboxes/
    approvals/
    settings/
  shared/
    components/            # Reusable UI primitives (no business logic)
    hooks/                 # useDebounce, usePagination
    api/                   # apiClient base, error handling
    types/                 # Branded types, shared enums
  app/
    routes.tsx             # React Router route definitions
    queryClient.ts         # TanStack Query client config
    theme.ts               # Mantine theme override
    App.tsx
  main.tsx
```

**Impact:** High -- Without this, cross-feature coupling degrades within weeks.
**Complexity:** XS -- Greenfield; zero migration cost.

---

### 2. TypeScript Strict Mode + Branded Types for Domain IDs

**Principle Violated:** Type Safety / Expressive Typing
**Reference:** Mirrors Python's `NewType("CorrelationId", UUID)` in `contracts/types.py:161-162`

```typescript
// tsconfig.json
{ "compilerOptions": { "strict": true, "noUncheckedIndexedAccess": true } }

// src/shared/types/branded.ts
declare const __brand: unique symbol;
type Brand<T, B> = T & { readonly [__brand]: B };

export type StreamId = Brand<string, 'StreamId'>;
export type WorkspaceId = Brand<string, 'WorkspaceId'>;
export type CredentialId = Brand<string, 'CredentialId'>;
export type CorrelationId = Brand<string, 'CorrelationId'>;
```

**Impact:** High -- Prevents ID-confusion bugs at compile time.
**Complexity:** XS

---

### 3. TanStack Query Key Factory Pattern

**Principle Violated:** DRY / Single Source of Truth

```typescript
// src/features/threads/api/queryKeys.ts
export const threadKeys = {
  all: ['threads'] as const,
  lists: () => [...threadKeys.all, 'list'] as const,
  list: (filters: ThreadFilters) => [...threadKeys.lists(), filters] as const,
  details: () => [...threadKeys.all, 'detail'] as const,
  detail: (id: StreamId) => [...threadKeys.details(), id] as const,
} satisfies Record<string, unknown>;
```

**Impact:** High -- Stale cache bugs are hard to debug in production.
**Complexity:** XS

---

### 4. Container / Presentational Component Separation

**Principle Violated:** Single Responsibility Principle

```typescript
// WorkflowTableContainer.tsx -- only data concerns
export function WorkflowTableContainer() {
  const { data = [], isLoading, error } = useWorkflows();
  return <WorkflowTable workflows={data} isLoading={isLoading} error={error?.message} />;
}

// WorkflowTable.tsx -- only rendering, fully testable with props
interface WorkflowTableProps {
  workflows: WorkflowSummary[];
  isLoading: boolean;
  error?: string;
}
export function WorkflowTable({ workflows, isLoading, error }: WorkflowTableProps) { ... }
```

**Impact:** High -- Enables unit testing of UI independently from network state.
**Complexity:** S

---

### 5. Error Boundary Strategy

**Principle Violated:** Error Handling / Fail Safely

Route-level error boundaries prevent full-page crashes. TanStack Query's `throwOnError` escalates to nearest boundary.

**Impact:** High -- Prevents full-page crashes; allows per-section recovery.
**Complexity:** S

---

### 6. API Client Abstraction Layer

**Principle Violated:** Dependency Inversion / Separation of Concerns
**Reference:** Mirrors `contracts/protocols.py` and `CorrelationMiddleware`

```typescript
// src/shared/api/client.ts
class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly correlationId?: CorrelationId,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  const correlationId = res.headers.get('X-Correlation-ID') as CorrelationId | null;
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText, correlationId ?? undefined);
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
```

**Impact:** High -- Single place for auth headers, error normalization, correlation ID logging.
**Complexity:** S

---

### 7. State Management -- No Server State in useState

**Principle Violated:** Single Source of Truth / DRY

**State Ownership Matrix:**
```
Server state (persisted remotely):      TanStack Query only
URL state (shareable, bookmarkable):    useSearchParams (filters, page, active tab)
Ephemeral UI state (non-shareable):     useState / useReducer (modal open, form draft)
Global UI state (non-server):           React context (sidebar collapsed, toasts)
```

**Impact:** High -- Prevents cache/state divergence.
**Complexity:** S

---

### 8. snake_case to camelCase Transform Layer

**Principle Violated:** Naming Consistency

Transform at the API boundary in `features/*/api/*.api.ts`, not in components.

```typescript
interface WorkflowStatusRaw { stream_id: string; workspace_id: string; phase: string; }

export interface WorkflowStatus {
  streamId: StreamId;
  workspaceId: WorkspaceId;
  phase: WorkflowPhase;
}

function toWorkflowStatus(raw: WorkflowStatusRaw): WorkflowStatus {
  return {
    streamId: raw.stream_id as StreamId,
    workspaceId: raw.workspace_id as WorkspaceId,
    phase: raw.phase as WorkflowPhase,
  };
}
```

**Impact:** Medium
**Complexity:** S

---

### 9. Form Validation with Mantine + Zod

**Principle Violated:** DRY / Consistency
**Reference:** Mirrors Pydantic request models in route files

```typescript
const startWorkflowSchema = z.object({
  workspaceId: z.string().min(1, 'Workspace ID is required'),
  channelId: z.string().min(1, 'Channel ID is required'),
  threadTs: z.string().min(1, 'Thread timestamp is required'),
  workflowType: z.enum(['feature_to_pr']),
});
```

**Impact:** Medium
**Complexity:** S

---

### 10. Testing Patterns (RTL + MSW)

**Principle Violated:** Testability / Maintainability

- Presentational components tested with React Testing Library (no network)
- Container/integration tests use MSW handlers
- Vitest + React Testing Library is the natural Vite-ecosystem pairing

**Impact:** High
**Complexity:** M

---

### 11. Accessibility Standards

**Principle Violated:** Accessibility / Universal Design (WCAG 2.1 AA)

- ARIA labels on all icon-only buttons
- Color + text on status badges (not color-only)
- Semantic wrapper on React Flow graph (`role="graphics-document"`)

**Impact:** Medium
**Complexity:** S-M

---

## Summary of Improvements

### High Priority
1. Feature-Based Folder Structure -- XS
2. TypeScript Strict Mode + Branded Types -- XS
3. TanStack Query Key Factory Pattern -- XS
4. Container / Presentational Separation -- S
5. API Client Abstraction Layer -- S
6. URL State for Filters / Pagination -- S

### Medium Priority
7. snake_case to camelCase Transform Layer -- S
8. Form Validation with Mantine + Zod -- S
9. Error Boundary Strategy -- S

### Low Priority
10. RTL + MSW Testing Patterns -- M
11. Accessibility Standards -- S-M

---

## Evidence Index

- [CLEAN-01] `contracts/types.py:161-162` -- Branded Types: Python uses `NewType`; mirror with TypeScript branded types
- [CLEAN-02] `contracts/types.py:27-100` -- Enum Constants: Python uses `StrEnum`; mirror with `const` object + union types
- [CLEAN-03] `contracts/protocols.py:1-285` -- Dependency Inversion: Protocol interfaces; mirror with TypeScript service interfaces
- [CLEAN-04] `api/routes/threads.py:1-19` -- SRP: Each route file has one concern and is ~20 lines
- [CLEAN-05] `api/routes/workflows.py:17-31` -- Request Models: Pydantic per endpoint; mirror with Zod schemas
- [CLEAN-06] `api/app.py:40-60` -- DI Pattern: `lifespan` injects dependencies; mirror with React context
- [CLEAN-07] `contracts/events.py:34-228` -- Naming Conventions: Past-tense event names, PascalCase types
- [CLEAN-08] `api/middleware/__init__.py` -- Cross-Cutting: Correlation middleware; API client must propagate this header
