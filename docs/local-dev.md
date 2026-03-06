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

## Database migrations

```bash
make migrate
```
