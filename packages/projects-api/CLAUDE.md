# lintel-projects-api

Project CRUD REST API routes and in-memory store, including engineering principles sub-resource.

## Structure

- `src/lintel/projects_api/store.py` — In-memory project store implementation
- `src/lintel/projects_api/routes.py` — FastAPI router + request/response models + principles sub-resource

## Principles Sub-Resource

Engineering principles (coding standards, review guidelines, architectural decisions) are stored as a list on the project dict. CRUD endpoints under `/projects/{project_id}/principles`.

## Testing

```bash
make test-projects-api
# or
uv run pytest packages/projects-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.projects_api.routes import project_store_provider
project_store_provider.override(stores["projects"])
```
