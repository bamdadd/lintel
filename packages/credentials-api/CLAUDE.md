# lintel-credentials-api

Credential CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/credentials_api/store.py` — In-memory credential store implementation
- `src/lintel/credentials_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-credentials-api
# or
uv run pytest packages/credentials-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.credentials_api.routes import credential_store_provider
credential_store_provider.override(stores["credentials"])
```
