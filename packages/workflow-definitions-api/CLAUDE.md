# lintel-workflow-definitions-api

Workflow definition REST API routes (CRUD for reusable workflow templates).

## Structure

- `src/lintel/workflow_definitions_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-workflow-definitions-api
# or
uv run pytest packages/workflow-definitions-api/tests/ -v
```

## DI Pattern

This package wires its dependencies through the app lifespan. See the app container for store wiring details.
