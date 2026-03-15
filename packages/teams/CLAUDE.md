# lintel-teams

Team CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/teams/store.py` — In-memory team store implementation
- `src/lintel/teams/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-teams
# or
uv run pytest packages/teams/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.teams.routes import team_store_provider
team_store_provider.override(stores["teams"])
```
