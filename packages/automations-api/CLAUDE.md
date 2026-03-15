# lintel-automations-api

Automation rule REST API routes, scheduler, and webhook hooks for event-triggered automations.

## Structure

- `src/lintel/automations_api/routes.py` — FastAPI router + request/response models
- `src/lintel/automations_api/scheduler.py` — Automation scheduler (cron-based triggering)
- `src/lintel/automations_api/hooks/` — Event hooks for automation triggering
- `src/lintel/automations_api/schemas.py` — Shared schema definitions

## Testing

```bash
make test-automations-api
# or
uv run pytest packages/automations-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.automations_api.routes import automation_store_provider
automation_store_provider.override(stores["automations"])
```
