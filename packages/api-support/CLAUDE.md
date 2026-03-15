# lintel-api-support

Shared utilities for all extracted API route packages: `StoreProvider`, `dispatch_event`, and store protocol types.

## Structure

- `src/lintel/api_support/provider.py` — `StoreProvider[T]`: lazy dependency holder, call `.override(store)` to wire and `.get()` to retrieve
- `src/lintel/api_support/event_dispatcher.py` — `dispatch_event`: fire-and-forget helper for publishing domain events
- `src/lintel/api_support/protocols.py` — `EntityStore` and `DictStore` Protocol types

## Testing

```bash
make test-api-support
# or
uv run pytest packages/api-support/tests/ -v
```

## Usage in extracted packages

```python
from lintel.api_support.provider import StoreProvider

my_store_provider: StoreProvider[MyStore] = StoreProvider()

# In app lifespan wiring:
my_store_provider.override(stores["my_store"])
```
