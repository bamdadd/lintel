# lintel-agent-definitions-api

Agent definition CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/agent_definitions_api/store.py` — In-memory agent definition store implementation
- `src/lintel/agent_definitions_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-agent-definitions-api
# or
uv run pytest packages/agent-definitions-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.agent_definitions_api.routes import agent_definition_store_provider
agent_definition_store_provider.override(stores["agent_definitions"])
```
