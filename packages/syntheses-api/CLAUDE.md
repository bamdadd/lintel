# lintel-syntheses-api

Synthesis CRUD REST API routes and in-memory store for REQ-034.3 cross-project synthesis.

## Structure

- `src/lintel/syntheses_api/store.py` — In-memory synthesis store
- `src/lintel/syntheses_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-syntheses-api
# or
uv run pytest packages/syntheses-api/tests/ -v
```
