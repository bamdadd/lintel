# lintel-users

User CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/users/store.py` — In-memory user store implementation
- `src/lintel/users/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-users
# or
uv run pytest packages/users/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.users.routes import user_store_provider
user_store_provider.override(stores["users"])
```
