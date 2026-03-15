# lintel-models-api

Model CRUD REST API routes and in-memory store (LLM model registry, distinct from lintel-models which does LLM routing).

## Structure

- `src/lintel/models_api/store.py` — In-memory model store implementation
- `src/lintel/models_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-models-api
# or
uv run pytest packages/models-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.models_api.routes import model_store_provider
model_store_provider.override(stores["models"])
```
