# lintel-memory-api

FastAPI router package exposing the Lintel memory subsystem over HTTP.

## Overview

Provides REST endpoints for creating, listing, searching, retrieving, and deleting
memory facts. Follows the ADR-001 API package pattern with StoreProvider-based
dependency injection and Pydantic request/response schemas.

## Key Components

- **routes.py** -- FastAPI `APIRouter` with CRUD and semantic-search endpoints under
  `/memory`.
- **schemas.py** -- Pydantic v2 models for request bodies and response payloads.
- **dependencies.py** -- `StoreProvider[MemoryService]` instance used for DI.

## Package Layout

Source lives under `src/lintel/memory_api/` (implicit namespace package -- no
`__init__.py` in `src/lintel/`). Follows ADR-001.
