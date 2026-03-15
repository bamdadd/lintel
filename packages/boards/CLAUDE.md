# lintel-boards

Board and tag CRUD REST API routes and in-memory stores.

## Structure

- `src/lintel/boards/store.py` — In-memory board and tag store implementations
- `src/lintel/boards/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-boards
# or
uv run pytest packages/boards/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real stores at startup:
```python
from lintel.boards.routes import board_store_provider, tag_store_provider
board_store_provider.override(stores["boards"])
tag_store_provider.override(stores["tags"])
```
