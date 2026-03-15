# lintel-policies-api

Policy CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/policies_api/store.py` — In-memory policy store implementation
- `src/lintel/policies_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-policies-api
# or
uv run pytest packages/policies-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.policies_api.routes import policy_store_provider
policy_store_provider.override(stores["policies"])
```
