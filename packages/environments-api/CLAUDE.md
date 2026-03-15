# lintel-environments-api

Environment CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/environments_api/store.py` — In-memory environment store implementation
- `src/lintel/environments_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-environments-api
# or
uv run pytest packages/environments-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.environments_api.routes import environment_store_provider
environment_store_provider.override(stores["environments"])
```
