# lintel-mcp-servers-api

MCP server CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/mcp_servers_api/store.py` — In-memory MCP server store implementation
- `src/lintel/mcp_servers_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-mcp-servers-api
# or
uv run pytest packages/mcp-servers-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.mcp_servers_api.routes import mcp_server_store_provider
mcp_server_store_provider.override(stores["mcp_servers"])
```
