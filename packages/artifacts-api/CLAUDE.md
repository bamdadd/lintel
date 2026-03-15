# lintel-artifacts-api

Code artifact and test result REST API routes and in-memory stores.

## Structure

- `src/lintel/artifacts_api/store.py` — In-memory artifact and test result store implementations
- `src/lintel/artifacts_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-artifacts-api
# or
uv run pytest packages/artifacts-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real stores at startup:
```python
from lintel.artifacts_api.routes import code_artifact_store_provider, test_result_store_provider
code_artifact_store_provider.override(stores["code_artifacts"])
test_result_store_provider.override(stores["test_results"])
```
