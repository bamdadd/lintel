# lintel-work-items-api

Work item CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/work_items_api/store.py` — In-memory work item store implementation
- `src/lintel/work_items_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-work-items-api
# or
uv run pytest packages/work-items-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.work_items_api.routes import work_item_store_provider
work_item_store_provider.override(stores["work_items"])
```
