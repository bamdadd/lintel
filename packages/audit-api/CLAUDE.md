# lintel-audit-api

Audit entry CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/audit_api/store.py` — In-memory audit entry store implementation
- `src/lintel/audit_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-audit-api
# or
uv run pytest packages/audit-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.audit_api.routes import audit_entry_store_provider
audit_entry_store_provider.override(stores["audit_entries"])
```
