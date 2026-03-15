# lintel-sandboxes-api

Sandbox lifecycle REST API routes (proxies to lintel-sandbox for Docker-based code execution).

## Structure

- `src/lintel/sandboxes_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-sandboxes-api
# or
uv run pytest packages/sandboxes-api/tests/ -v
```

## DI Pattern

This package delegates to `lintel-sandbox` (SandboxManager). Dependencies are wired through the app lifespan via the AppContainer.
