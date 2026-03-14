# lintel-event-bus

Async pub/sub event bus with gap-free catch-up subscriptions — in-memory backend.

## Key exports

- `InMemoryEventBus` — Implements `EventBus` protocol; per-subscriber `asyncio.Queue`, event-type filtering, failed handlers logged but never blocking
- `CatchUpSubscription` (in `subscriptions.py`) — subscribes to bus first (buffers live), replays history from store, drains buffer deduped by `event_id`
- `LiveSubscription` — thin wrapper for live-only bus subscriptions

## Dependencies

- `lintel-contracts` — `EventEnvelope`, `EventBus`, `EventHandler`, `EventStore` protocols
- `structlog>=24.4`

## Tests

```bash
make test-event-bus
# or: uv run pytest packages/event-bus/tests/ -v
```

## Usage

```python
from lintel.event_bus.in_memory import InMemoryEventBus
from lintel.event_bus.subscriptions import CatchUpSubscription

bus = InMemoryEventBus()
sub_id = await bus.subscribe({"ThreadMessageReceived"}, handler)
await bus.publish(envelope)
await bus.unsubscribe(sub_id)
```
