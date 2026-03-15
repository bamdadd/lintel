# lintel-chat-api

Chat conversation REST API routes, ChatService (routing + workflow dispatch), and in-memory chat store.

## Structure

- `src/lintel/chat_api/routes.py` — FastAPI router + request/response models
- `src/lintel/chat_api/chat_router.py` — `ChatService`: classifies messages, dispatches workflows

## Testing

```bash
make test-chat-api
# or
uv run pytest packages/chat-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.chat_api.routes import chat_store_provider
chat_store_provider.override(stores["chat"])
```
