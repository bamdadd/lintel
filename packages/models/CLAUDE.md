# lintel-models

LLM provider abstraction with routing, caching, and streaming — backed by litellm.

## Key exports

- `DefaultModelRouter` — implements `ModelRouter` protocol; selects `ModelPolicy` (provider + model + context window + temperature) per `AgentRole` and workload type; supports SQLite response cache
- `FALLBACK_POLICY` — default `ModelPolicy("ollama", "llama3.1:8b", 4096, 0.0)` used when no assignment matches
- `ClaudeCodeClient` (in `claude_code.py`) — direct Claude API client used for `claude_code` agent role

## Dependencies

- `lintel-contracts` — `ModelPolicy`, `AgentRole`, `ModelRouter` protocol
- `litellm>=1.55`, `httpx>=0.28`, `tenacity>=9.0`, `structlog>=24.4`

## Tests

```bash
make test-models
# or: uv run pytest packages/models/tests/ -v
```

## Usage

```python
from lintel.models.router import DefaultModelRouter

router = DefaultModelRouter(
    model_store=model_store,
    ai_provider_store=ai_provider_store,
    model_assignment_store=model_assignment_store,
    ollama_api_base="http://localhost:11434",
)
policy = await router.get_policy(role="coder", workload="implement")
response = await router.complete(messages, policy)
```
