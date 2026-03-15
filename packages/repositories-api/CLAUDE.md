# lintel-repositories-api

Repository registration REST API routes (registers GitHub/GitLab repos with Lintel).

## Structure

- `src/lintel/repositories_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-repositories-api
# or
uv run pytest packages/repositories-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.repositories_api.routes import repository_store_provider
repository_store_provider.override(stores["repositories"])
```
