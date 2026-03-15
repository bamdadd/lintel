# lintel-approval-requests-api

Approval request CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/approval_requests_api/store.py` — In-memory approval request store implementation
- `src/lintel/approval_requests_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-approval-requests-api
# or
uv run pytest packages/approval-requests-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.approval_requests_api.routes import approval_request_store_provider
approval_request_store_provider.override(stores["approval_requests"])
```
