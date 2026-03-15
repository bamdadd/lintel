# lintel-experimentation-api

KPI, experiment, and compliance metric REST API routes.

## Structure

- `src/lintel/experimentation_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-experimentation-api
# or
uv run pytest packages/experimentation-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.experimentation_api.routes import kpi_store_provider
kpi_store_provider.override(stores["experimentation"])
```
