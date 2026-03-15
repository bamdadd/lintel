# lintel-skills-api

Skill CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/skills_api/store.py` — In-memory skill store implementation
- `src/lintel/skills_api/routes.py` — FastAPI router + request/response models
- `src/lintel/skills_api/domain/` — Domain logic for skill invocation

## Testing

```bash
make test-skills-api
# or
uv run pytest packages/skills-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.skills_api.routes import skill_store_provider
skill_store_provider.override(stores["skills"])
```
