# lintel-notifications-api

Notification rule CRUD REST API routes and in-memory store.

## Structure

- `src/lintel/notifications_api/store.py` — In-memory notification rule store implementation
- `src/lintel/notifications_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-notifications-api
# or
uv run pytest packages/notifications-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.notifications_api.routes import notification_rule_store_provider
notification_rule_store_provider.override(stores["notification_rules"])
```
