# lintel-pipelines-api

Pipeline run and stage REST API routes, SSE event delivery loop, and in-memory pipeline store.

## Structure

- `src/lintel/pipelines_api/routes.py` — FastAPI router + request/response models, SSE endpoint
- `src/lintel/pipelines_api/delivery_loop/` — SSE event streaming logic for real-time stage updates

## Testing

```bash
make test-pipelines-api
# or
uv run pytest packages/pipelines-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.pipelines_api.routes import pipeline_store_provider
pipeline_store_provider.override(stores["pipelines"])
```
