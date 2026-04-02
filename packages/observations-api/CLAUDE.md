# lintel-observations-api

Observation CRUD REST API routes and in-memory store for REQ-034.3 run observation capture.

## Structure

- `src/lintel/observations_api/store.py` — In-memory observation store
- `src/lintel/observations_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-observations-api
# or
uv run pytest packages/observations-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup.
