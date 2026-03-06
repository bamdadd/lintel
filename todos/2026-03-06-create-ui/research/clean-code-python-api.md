# Clean Code Analysis - python-api

## Analysis Scope

**Tech Area:** python-api
**Task Context:** Build a React SPA that consumes the existing FastAPI backend -- analyze API code quality for UI integration readiness.
**Analysis Date:** 2026-03-06
**Clean Code Docs:** No clean code docs found for python-api -- built-in principles applied.

---

## Violations & Improvements

### 1. All Endpoints Return `dict[str, Any]` -- No Typed Response Models

**Issue:** Every route handler across all 15 route files returns `dict[str, Any]` or `list[dict[str, Any]]`. The generated OpenAPI schema is `{}` (empty object), producing a completely unusable TypeScript client.

**Principle Violated:** Type Safety / OpenAPI Contract Integrity

**Files Affected:** All 40 endpoints across 15 files.

**Example -- `src/lintel/api/routes/threads.py:13-18`:**
```python
@router.get("/threads")
async def list_threads(
    projection: Annotated[ThreadStatusProjection, Depends(get_thread_status_projection)],
) -> list[dict[str, Any]]:
    return projection.get_all()
```

**Proposed Improvement:**
```python
class ThreadStatusResponse(BaseModel):
    stream_id: str
    workspace_id: str
    channel_id: str
    thread_ts: str
    phase: str
    updated_at: str

@router.get("/threads", response_model=list[ThreadStatusResponse])
async def list_threads(...) -> list[ThreadStatusResponse]:
    return [ThreadStatusResponse(**item) for item in projection.get_all()]
```

**Impact:** High -- Without typed response models, TypeScript client generation produces `Record<string, unknown>` for every endpoint.
**Complexity:** M -- Requires ~20-25 Pydantic response models.

---

### 2. No CORS Middleware -- Hard Blocks All Browser Requests

**Issue:** `app.py` adds only `CorrelationMiddleware`. No `CORSMiddleware`. Every browser request from a different origin is blocked.

**Principle Violated:** API completeness for web clients

**File:** `src/lintel/api/app.py:63-82`

**Impact:** High -- Hard blocker for UI development.
**Complexity:** XS -- Three lines plus an environment variable.

---

### 3. No Authentication or Security Scheme

**Issue:** No auth mechanism defined anywhere. `/admin/reset-projections` is unprotected.

**Principle Violated:** Security, API contract completeness

**Impact:** High -- Security risk; UI has no auth contract.
**Complexity:** S

---

### 4. DRY Violation -- ThreadRef Construction Repeated Across 8 Route Files

**Issue:** Same `ThreadRef(workspace_id=..., channel_id=..., thread_ts=...)` appears in 5 route files (~8 handlers). Each request model independently re-declares the three fields.

**Principle Violated:** DRY

**Files Affected:** workflows.py, agents.py, approvals.py, sandboxes.py, pii.py

**Proposed Improvement:**
```python
class ThreadScopedRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str

    def to_thread_ref(self) -> ThreadRef:
        return ThreadRef(
            workspace_id=self.workspace_id,
            channel_id=self.channel_id,
            thread_ts=self.thread_ts,
        )
```

**Impact:** Medium
**Complexity:** S

---

### 5. Infrastructure Classes Inside Route Files -- SRP Violation

**Issue:** `InMemoryCredentialStore` lives in `credentials.py` and `InMemorySkillStore` lives in `skills.py`. `app.py` imports infrastructure from route modules -- reversed dependency.

**Principle Violated:** Single Responsibility Principle, Separation of Concerns

**Files:** `credentials.py:14-53`, `skills.py:19-57`, `app.py:28-29`

**Impact:** Medium
**Complexity:** S

---

### 6. Inconsistent Dependency Injection -- Lazy `hasattr` Init in 7 Functions

**Issue:** Some routes use centralized `deps.py` injectors; 6 other route files define their own `get_*` dependency functions with lazy `hasattr` initialization.

**Principle Violated:** DRY, Consistency, Predictable Initialization

**Files:** agents.py, sandboxes.py, settings.py, metrics.py, workflow_definitions.py, pii.py

**Impact:** Medium
**Complexity:** S

---

### 7. Placeholder Endpoints Returning HTTP 200 with Stub Data

**Issue:** `GET /events/stream/{stream_id}` and `GET /events/correlation/{correlation_id}` return `{"events": [], "note": "Placeholder..."}` with HTTP 200. UI will silently render empty timelines.

**Principle Violated:** Honest API contract, Error Handling

**File:** `src/lintel/api/routes/events.py:28-55`

**Impact:** Medium -- Should return 501 instead.
**Complexity:** XS

---

### 8. Verb-in-Path REST Convention Violations

**Issue:** `POST /approvals/grant`, `POST /approvals/reject`, `POST /pii/reveal` use verb-in-path style. All other resources use standard noun-based paths.

**Principle Violated:** REST Uniform Interface

**Impact:** Medium
**Complexity:** S

---

### 9. `GET /threads` and `GET /workflows` Return Identical Data

**Issue:** Both call `projection.get_all()` on the same `ThreadStatusProjection`, returning identical data. One is redundant.

**Principle Violated:** DRY, API surface clarity

**Files:** `threads.py:13-18`, `workflows.py:50-55`

**Impact:** Medium -- Confuses UI developers about which endpoint is canonical.
**Complexity:** XS

---

### 10. `POST /workflows/messages` Path Conflict with `/{stream_id}`

**Issue:** Static segment `messages` collides with `{stream_id}` parameter space. A `GET /workflows/messages` added later would shadow `GET /workflows/{stream_id}` for `stream_id = "messages"`.

**Principle Violated:** REST Resource Design

**File:** `workflows.py:58,71`

**Impact:** Medium -- Latent routing conflict.
**Complexity:** XS

---

## Summary of Improvements

### High Priority (Directly blocks UI integration)
1. **No CORS Middleware** -- XS
2. **No Typed Response Models** -- M
3. **No Authentication Scheme** -- S
4. **Duplicate GET /threads and GET /workflows** -- XS

### Medium Priority
5. **Placeholder 200 Responses on Event Endpoints** -- XS
6. **Verb-in-Path Routes** -- S
7. **POST /workflows/messages Path Conflict** -- XS
8. **Inconsistent Dependency Injection / Lazy Init** -- S

### Low Priority
9. **ThreadRef Construction Duplicated** -- S
10. **Infrastructure Classes in Route Files** -- S

---

## Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Endpoints with typed response models | 0 / 40 | 40 / 40 |
| CORS configured | No | Yes |
| Authentication scheme defined | None | API key or JWT |
| Duplicate endpoint pairs | 1 | 0 |
| Placeholder 200 endpoints | 2 | 0 |
| Lazy `hasattr` init functions | 7 | 0 |
| Infrastructure classes in route files | 2 | 0 |

---

## Anti-Pattern Check

| Anti-Pattern | Found | Count | Severity |
|--------------|-------|-------|----------|
| `dict[str, Any]` as response type | Yes | 40 endpoints | High |
| Missing CORS middleware | Yes | 1 (app-level) | High |
| No authentication scheme | Yes | All routes | High |
| Lazy `hasattr` state init | Yes | 7 functions | Medium |
| Verb in REST path | Yes | 3 routes | Medium |
| Infrastructure class in route layer | Yes | 2 classes | Medium |
| Duplicate endpoint surfaces | Yes | 1 pair | Medium |
| Placeholder 200 responses | Yes | 2 endpoints | Medium |

---

## Evidence Index

[CLEAN-01] `src/lintel/api/routes/threads.py:16` -- Type Safety: `list[dict[str, Any]]` produces empty OpenAPI schema
[CLEAN-02] `src/lintel/api/routes/workflows.py:36,53,62,74` -- Type Safety: all workflow handlers return untyped dicts
[CLEAN-03] `src/lintel/api/routes/agents.py:48-116` -- Type Safety: all 6 agent handlers return `dict[str, Any]`
[CLEAN-04] `src/lintel/api/app.py:63-82` -- Security/CORS: no `CORSMiddleware` added
[CLEAN-05] `src/lintel/api/app.py:63-82` -- Security: no authentication scheme declared
[CLEAN-06] `src/lintel/api/routes/admin.py:13-19` -- Security: danger-zone endpoint has no auth guard
[CLEAN-07] `src/lintel/api/routes/events.py:28-55` -- Error Handling: placeholder returns HTTP 200 with stub data
[CLEAN-08] `src/lintel/api/routes/approvals.py:33,50` -- REST: verb-in-path
[CLEAN-09] `src/lintel/api/routes/pii.py:45` -- REST: verb-in-path
[CLEAN-10] `threads.py:13-18` + `workflows.py:50-55` -- DRY: duplicate endpoints
[CLEAN-11] `workflows.py:58,71` -- REST: static `/messages` collides with `/{stream_id}`
[CLEAN-12] `sandboxes.py:17-21` -- DRY/SRP: lazy `hasattr` init
[CLEAN-13] `workflow_definitions.py:12-56` -- SRP: seed data embedded in dependency function
[CLEAN-14] `credentials.py:14-53` -- SRP: `InMemoryCredentialStore` in a route file
[CLEAN-15] `skills.py:19-57` -- SRP: `InMemorySkillStore` in a route file
[CLEAN-16] `app.py:28-29` -- SRP: `app.py` imports infrastructure from route modules
[CLEAN-17] `approvals.py:15-39` -- DRY: `workspace_id/channel_id/thread_ts` repeated across all thread-scoped request models
