# lintel-ai-providers-api

AI provider CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/ai_providers_api/store.py` — In-memory AI provider store implementation
- `src/lintel/ai_providers_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-ai-providers-api
# or
uv run pytest packages/ai-providers-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.ai_providers_api.routes import ai_provider_store_provider
ai_provider_store_provider.override(stores["ai_providers"])
```
