# lintel-variables-api

Variable CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/variables_api/store.py` — In-memory variable store implementation
- `src/lintel/variables_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-variables-api
# or
uv run pytest packages/variables-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.variables_api.routes import variable_store_provider
variable_store_provider.override(stores["variables"])
```
