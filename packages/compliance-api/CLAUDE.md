# lintel-compliance-api

Compliance policy, regulation, practice, procedure, strategy, and knowledge entry REST API routes and in-memory stores.

## Structure

- `src/lintel/compliance_api/store.py` — In-memory compliance store implementations
- `src/lintel/compliance_api/routes.py` — FastAPI router + request/response models
- `src/lintel/compliance_api/guardrail_rules.py` — Guardrail rule CRUD endpoints
- `src/lintel/compliance_api/seed.py` — Seed data for built-in regulation templates

## Testing

```bash
make test-compliance-api
# or
uv run pytest packages/compliance-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.compliance_api.routes import regulation_store_provider
regulation_store_provider.override(stores["compliance"])
```
