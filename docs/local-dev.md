# Local Development

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for integration tests and local dev environment)

## Quick start

```bash
# Install dependencies
make install

# Run unit tests (no Docker required)
make test-unit

# Run all checks
make all
```

## Docker Compose

For a full local environment with Postgres and NATS:

```bash
# Set up environment
cp .env.example .env
# Edit .env with your Slack credentials (optional for local dev)

# Start services
cd ops && docker compose up -d

# Check health
curl http://localhost:8000/healthz

# View logs
cd ops && docker compose logs -f lintel

# Stop
cd ops && docker compose down
```

### Services

| Service | Port | Description |
|---|---|---|
| Postgres | 5432 | Event store and PII vault |
| NATS | 4222, 8222 | Message bus (JetStream) |
| Lintel | 8000 | API server |

## Running tests

```bash
make test-unit         # Fast, no external deps
make test-integration  # Needs Docker (uses testcontainers)
make test              # All tests
```

## Local Ollama models

To use a local Ollama instance as a model provider:

1. Install and start [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull llama3.1:8b`
3. Set environment variables (or add to `.env`):

```bash
export LINTEL_MODEL_FALLBACK_PROVIDER=ollama
export LINTEL_MODEL_FALLBACK_MODEL=llama3.1:8b
export LINTEL_MODEL_OLLAMA_API_BASE=http://localhost:11434
```

Ollama is configured as the default fallback provider. When the primary provider
(Anthropic) is unavailable or a role has no explicit routing entry, the router
falls back to the local Ollama model.

## Database migrations

```bash
make migrate
```
