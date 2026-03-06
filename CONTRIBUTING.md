# Contributing to Lintel

## Setup

1. Install [uv](https://docs.astral.sh/uv/)
2. Clone the repository
3. Run `make install` to install all dependencies

## Development workflow

```bash
make format     # Auto-fix formatting
make lint       # Check linting (ruff)
make typecheck  # Run mypy strict mode
make test-unit  # Run unit tests (fast, no external deps)
make all        # Run everything
```

## Code style

- **Ruff** with strict rules (E, F, W, I, N, UP, ANN, B, A, SIM, TCH, RUF), line length 100
- **mypy** strict mode with pydantic plugin
- Use `from __future__ import annotations` in all modules
- Put type-only imports in `TYPE_CHECKING` blocks

## Architecture rules

- **Contracts** (`src/lintel/contracts/`) are pure — no I/O, no infrastructure imports
- **Domain** code depends only on contracts (Protocol interfaces)
- **Infrastructure** implements Protocol interfaces
- Never import infrastructure from domain or contracts
- No Slack types outside `infrastructure/channels/slack/`
- No LangGraph imports outside `workflows/`

## Testing

- Unit tests go in `tests/unit/` — no external dependencies
- Integration tests go in `tests/integration/` — use testcontainers
- Use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)

## Commits

Use the format: `[LINTEL] description of change`

## Pull requests

- All CI checks must pass (lint, typecheck, test-unit, test-integration)
- Keep PRs focused on a single concern
