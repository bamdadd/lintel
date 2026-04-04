# lintel-multi-tenancy-api

Workspace isolation middleware and workspace CRUD routes.

## Structure

- `src/lintel/multi_tenancy_api/middleware.py` — `WorkspaceIsolationMiddleware`: extracts workspace_id from X-Workspace-Id header or JWT claim
- `src/lintel/multi_tenancy_api/routes.py` — Workspace CRUD (POST/GET /workspaces, GET /workspaces/{id})
- `src/lintel/multi_tenancy_api/store.py` — `InMemoryWorkspaceStore` + `Workspace` dataclass

## Testing

```bash
make test-multi-tenancy-api
# or
uv run pytest packages/multi-tenancy-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.multi_tenancy_api.routes import workspace_store_provider
workspace_store_provider.override(stores["workspace_store"])
```
