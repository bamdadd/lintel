# lintel-audit-api

Audit entry CRUD REST API routes with tamper-proof hash chain.

## Structure

- `src/lintel/audit_api/store.py` — In-memory audit entry store implementation
- `src/lintel/audit_api/hash_chain.py` — SHA-256 hash chain store with verification and export
- `src/lintel/audit_api/routes.py` — FastAPI router + verify/export endpoints

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
