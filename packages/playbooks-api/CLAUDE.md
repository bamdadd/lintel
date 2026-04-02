# lintel-playbooks-api

Playbook CRUD REST API routes and in-memory store for REQ-034.3 playbook curation.

## Structure

- `src/lintel/playbooks_api/store.py` — In-memory playbook store
- `src/lintel/playbooks_api/routes.py` — FastAPI router + request/response models

## Testing

```bash
make test-playbooks-api
# or
uv run pytest packages/playbooks-api/tests/ -v
```
