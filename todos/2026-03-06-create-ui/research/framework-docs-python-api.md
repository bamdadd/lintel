# Framework Documentation Research - python-api

## Research Scope

**Tech Area:** python-api
**Frameworks:** FastAPI (0.115+), Pydantic v2 (2.x), Starlette (underlying ASGI)
**Task Context:** Build a React SPA that consumes a FastAPI backend -- need patterns for serving SPAs, generating API clients, CORS, SSE/WebSocket streaming, and Pydantic response models
**Research Date:** 2026-03-06

---

## Framework: FastAPI

### Relevant Patterns

**Pattern: StaticFiles mounting for SPA serving**
- **Documentation:** FastAPI / Starlette Static Files + catch-all route
- **Description:** Mount `StaticFiles` for assets, then add a catch-all `GET` route that returns `index.html` for any unmatched path. This lets the React router handle client-side navigation while FastAPI serves the API under `/api/`.
- **Code Example:**
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

FRONTEND_DIST = Path("frontend/dist")

app = FastAPI()

# All API routers registered first
app.include_router(threads.router, prefix="/api/v1", tags=["threads"])

# Mount React build assets
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

# Catch-all: serve index.html for any non-API path
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str) -> FileResponse:
    return FileResponse(FRONTEND_DIST / "index.html")
```
- **Applicability:** HIGH -- required to host a React SPA from the same FastAPI server
- **Evidence:** [DOCS-1]

**Pattern: CORSMiddleware configuration**
- **Documentation:** FastAPI / Starlette Middleware -- CORS
- **Description:** `CORSMiddleware` must be added before any route handling. In development, allow the Vite dev server origin; in production, restrict to the deployed domain.
- **Code Example:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "https://app.example.com",  # production origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],  # expose custom headers to JS
)
```
- **Applicability:** HIGH -- cross-origin requests from the Vite dev server will fail without this
- **Evidence:** [DOCS-2]

**Pattern: OpenAPI schema customization and operation ID control**
- **Documentation:** FastAPI -- Extending OpenAPI / Custom OpenAPI
- **Description:** Use `generate_unique_id_function` to control operation IDs -- critical for clean TypeScript client generation (operation IDs become function names).
- **Code Example:**
```python
from fastapi.routing import APIRoute

def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"

app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```
- **Applicability:** HIGH -- clean operation IDs are essential for a usable generated TypeScript client
- **Evidence:** [DOCS-3]

**Pattern: Server-Sent Events (SSE) streaming**
- **Documentation:** FastAPI -- StreamingResponse / Custom Response Classes
- **Description:** Use `StreamingResponse` with `media_type="text/event-stream"` and an async generator. SSE is preferable over WebSockets for unidirectional server-push (workflow status updates, log tailing).
- **Code Example:**
```python
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

async def workflow_event_generator(thread_id: str):
    try:
        while True:
            payload = json.dumps({"thread_id": thread_id, "phase": "planning"})
            yield f"data: {payload}\n\n"
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        yield "data: [DONE]\n\n"

@router.get("/threads/{thread_id}/stream")
async def stream_thread_events(thread_id: str) -> StreamingResponse:
    return StreamingResponse(
        workflow_event_generator(thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```
- **Applicability:** HIGH -- natural fit for pushing WorkflowPhase transitions to the React UI
- **Evidence:** [DOCS-4]

**Pattern: WebSocket endpoint for bidirectional communication**
- **Documentation:** FastAPI -- WebSockets
- **Description:** Use `@router.websocket` for bidirectional real-time communication. Suited for human-in-the-loop approval flows.
- **Applicability:** MEDIUM -- SSE covers most read-only streaming; WebSocket is valuable for approval flows
- **Evidence:** [DOCS-5]

### Best Practices

**Response Models and Pydantic Integration**
- Always declare `response_model` or annotate the return type -- FastAPI validates and filters output
- Use `response_model_exclude_none=True` to omit null fields
- Prefer returning Pydantic model instances over raw `dict`
- **Evidence:** [DOCS-6]

**Dependency Injection**
- Use `Annotated[T, Depends(fn)]` (current idiomatic form)
- Lifespan state (`app.state.*`) should be accessed through a dependency factory
- **Evidence:** [DOCS-7]

**Router Organization**
- Use `APIRouter(prefix="/...", tags=["..."])` for self-contained route modules
- Set `tags` on the router (not individual routes) for consistent OpenAPI grouping
- **Evidence:** [DOCS-8]

---

## Framework: Pydantic v2

### Relevant Patterns

**Pattern: BaseModel with ConfigDict for API response contracts**
- **Description:** `ConfigDict` replaces inner `class Config`. Key settings: `from_attributes=True` (construct from frozen dataclasses), `populate_by_name=True`.
- **Code Example:**
```python
from pydantic import BaseModel, ConfigDict, Field

class ThreadStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    thread_id: str = Field(description="Canonical stream ID")
    phase: str = Field(description="Current WorkflowPhase value")
```
- **Applicability:** HIGH -- needed to convert existing frozen dataclasses to serializable API responses
- **Evidence:** [DOCS-10]

**Pattern: field_serializer for non-JSON-native domain types**
- **Description:** Use `@field_serializer` to customize how `frozenset`, `UUID`, and custom types serialize to JSON.
- **Code Example:**
```python
from pydantic import BaseModel, field_serializer
from uuid import UUID

class EventEnvelopeResponse(BaseModel):
    event_id: UUID
    repo_ids: frozenset[str]

    @field_serializer("event_id")
    def serialize_uuid(self, v: UUID) -> str:
        return str(v)

    @field_serializer("repo_ids")
    def serialize_frozenset(self, v: frozenset[str]) -> list[str]:
        return sorted(v)
```
- **Applicability:** HIGH -- the Lintel codebase uses `frozenset`, `UUID`, and frozen dataclasses throughout
- **Evidence:** [DOCS-12]

**Pattern: Discriminated unions for polymorphic event types**
- **Description:** Use `Annotated[Union[...], Field(discriminator="event_type")]` to route deserialization based on a literal field. Produces clean `anyOf` + discriminator in OpenAPI 3.1.
- **Applicability:** MEDIUM -- the `/events` endpoint returns heterogeneous event types
- **Evidence:** [DOCS-13]

---

## Integration Patterns

**Pattern: Generating a TypeScript API client from OpenAPI**
- **Description:** FastAPI auto-generates an OpenAPI 3.1 schema at `/openapi.json`. Feed this to `openapi-typescript` to generate typed interfaces, or `@hey-api/openapi-ts` for a full request client.
- **Code Example:**
```bash
# Generate TypeScript types only
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts

# Generate full typed client
npx @hey-api/openapi-ts \
  --input http://localhost:8000/openapi.json \
  --output src/api/client \
  --client @hey-api/client-fetch
```
- **Applicability:** HIGH -- eliminates manual TypeScript interface maintenance
- **Evidence:** [DOCS-16]

**Pattern: SPA production layout -- full create_app() example**
- **Description:** Build React to `frontend/dist/`, mount static assets, register all API routers, then add the SPA catch-all last.
- **Code Example:**
```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_DIST = Path("frontend/dist")

def create_app() -> FastAPI:
    app = FastAPI(title="Lintel", version="0.1.0", lifespan=lifespan)

    # 1. Middleware first
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)
    app.add_middleware(CorrelationMiddleware)

    # 2. All API routers
    app.include_router(threads.router, prefix="/api/v1", tags=["threads"])
    # ... other routers

    # 3. Static assets (only in production)
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

    return app
```
- **Applicability:** HIGH -- production deployment pattern for co-located React + FastAPI
- **Evidence:** [DOCS-17]

---

## Anti-Patterns (What NOT to Do)

1. **Wildcard catch-all registered before API routes** -- All API calls silently return HTML [DOCS-18]
2. **`allow_origins=["*"]` with `allow_credentials=True`** -- Browsers reject this combination [DOCS-19]
3. **Returning raw `dict` from endpoints** -- TypeScript client loses all type information [DOCS-20]
4. **Blocking synchronous I/O in async path operations** -- Stalls entire event loop [DOCS-21]
5. **Pydantic v1 `class Config` in v2 models** -- Deprecation warnings, subtle bugs [DOCS-22]

---

## Idiomatic Patterns Summary

### High Priority (Must do)
1. Register all API routers before the SPA catch-all route [DOCS-18]
2. Use explicit `allow_origins` list in CORSMiddleware [DOCS-2]
3. Define Pydantic `BaseModel` response schemas for all endpoints [DOCS-20]
4. Use `generate_unique_id_function` to control OpenAPI operation IDs [DOCS-3]
5. Use `ConfigDict(from_attributes=True)` on response models [DOCS-10]

### Medium Priority (Should do)
6. Use `@field_serializer` for non-JSON-native domain types [DOCS-12]
7. Use SSE (`StreamingResponse`) for workflow phase push [DOCS-4]
8. Use `response_model_exclude_none=True` on endpoints with many optional fields [DOCS-6]
9. Use discriminated unions for the `/events` endpoint [DOCS-13]

---

## Evidence Index

[DOCS-1] Official Docs - StaticFiles + SPA catch-all (FastAPI / Starlette, v0.115, 2026)
[DOCS-2] Official Docs - CORSMiddleware configuration (FastAPI, v0.115, 2026)
[DOCS-3] Official Docs - Custom OpenAPI schema / generate_unique_id_function (FastAPI, v0.115, 2026)
[DOCS-4] Official Docs - StreamingResponse / SSE (FastAPI / Starlette, v0.115, 2026)
[DOCS-5] Official Docs - WebSocket endpoints (FastAPI, v0.115, 2026)
[DOCS-6] Official Docs - Response Model / response_model_exclude_none (FastAPI, v0.115, 2026)
[DOCS-7] Official Docs - Dependencies / Annotated + Depends (FastAPI, v0.115, 2026)
[DOCS-8] Official Docs - Bigger Applications / APIRouter (FastAPI, v0.115, 2026)
[DOCS-9] Official Docs - Lifespan Events (FastAPI, v0.115, 2026)
[DOCS-10] Official Docs - Model Config / ConfigDict (Pydantic, v2.x, 2026)
[DOCS-11] Official Docs - JSON Schema generation / model_json_schema (Pydantic, v2.x, 2026)
[DOCS-12] Official Docs - Custom field serializers / @field_serializer (Pydantic, v2.x, 2026)
[DOCS-13] Official Docs - Discriminated Unions (Pydantic, v2.x, 2026)
[DOCS-14] Official Docs - Pydantic v2 Migration Guide (Pydantic, v2.x, 2026)
[DOCS-15] Official Docs - Field / Annotated validators (Pydantic, v2.x, 2026)
[DOCS-16] Official Docs - OpenAPI client generation / openapi-typescript (FastAPI + openapi-typescript, 2026)
[DOCS-17] Official Docs - SPA production layout with StaticFiles (FastAPI / Starlette, v0.115, 2026)
[DOCS-18] Official Docs - Path parameter ordering / catch-all anti-pattern (FastAPI, v0.115, 2026)
[DOCS-19] Official Docs - CORS credentials anti-pattern (FastAPI + MDN CORS spec, 2026)
[DOCS-20] Official Docs - Response model dict anti-pattern (FastAPI, v0.115, 2026)
[DOCS-21] Official Docs - Async / blocking code anti-pattern (FastAPI, v0.115, 2026)
[DOCS-22] Official Docs - Pydantic v1 Config class deprecation (Pydantic, v2.x, 2026)
[DOCS-23] Official Docs - FastAPI changelog + Pydantic v2 migration (FastAPI 0.93-0.115; Pydantic v2.x, 2026)
