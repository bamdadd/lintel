# lintel-triggers-api

Trigger CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/triggers_api/store.py` — In-memory trigger store implementation
- `src/lintel/triggers_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-triggers-api
# or
uv run pytest packages/triggers-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.triggers_api.routes import trigger_store_provider
trigger_store_provider.override(stores["triggers"])
```
