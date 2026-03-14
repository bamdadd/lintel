# lintel-observability

Structured logging, OpenTelemetry tracing, metrics, and correlation ID propagation.

## Key exports

- `configure_logging` (in `logging.py`) — configures structlog with JSON or console output, merges contextvars
- `configure_tracing` (in `tracing.py`) — sets up OpenTelemetry `TracerProvider` with optional OTLP exporter
- `get_correlation_id` / `set_correlation_id` (in `correlation.py`) — `ContextVar`-based correlation ID for request tracing
- `correlation_id_var` — the raw `ContextVar[UUID]` for direct manipulation
- `StepMetrics` (in `step_metrics.py`) — per-step timing and counters for workflow nodes
- `MetricsCollector` (in `metrics.py`) — aggregates agent/quality/PII metrics

## Dependencies

- `lintel-contracts`
- `opentelemetry-sdk>=1.29`, `opentelemetry-exporter-otlp>=1.29`, `structlog>=24.4`

## Tests

```bash
make test-observability
# or: uv run pytest packages/observability/tests/ -v
```

## Usage

```python
from lintel.observability.logging import configure_logging
from lintel.observability.tracing import configure_tracing
from lintel.observability.correlation import get_correlation_id, set_correlation_id

configure_logging(log_level="INFO", log_format="json")
tracer = configure_tracing(otel_endpoint="http://localhost:4317")
cid = get_correlation_id()  # auto-generates UUID if not set
```
