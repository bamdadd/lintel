# lintel-knowledge-api

Knowledge graph edge CRUD and DAG traversal REST API routes (REQ-034.3).

## Structure

- `src/lintel/knowledge_api/store.py` — In-memory knowledge edge store with graph traversal
- `src/lintel/knowledge_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-knowledge-api
# or
uv run pytest packages/knowledge-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup.
