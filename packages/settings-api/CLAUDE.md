# lintel-settings-api

Settings and connection management REST API routes.

## Structure

- `src/lintel/settings_api/routes.py` — FastAPI router + request/response models for settings and connections

## Testing

```bash
make test-settings-api
# or
uv run pytest packages/settings-api/tests/ -v
```

## DI Pattern

This package wires its dependencies through the app lifespan. See the app container for store wiring details.
