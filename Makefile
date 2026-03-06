.PHONY: help install test test-unit test-integration test-e2e lint typecheck format serve migrate all

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-extras

test: ## Run all tests (pass ARGS= for extra pytest flags)
	uv run pytest $(ARGS)

test-unit: ## Run unit tests
	uv run pytest tests/unit -v

test-integration: ## Run integration tests
	uv run pytest tests/integration -v

test-e2e: ## Run e2e tests
	uv run pytest tests/e2e -v

lint: ## Check linting and formatting
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

typecheck: ## Run mypy strict type checking
	uv run mypy src/lintel/

format: ## Auto-fix formatting and lint
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

serve: ## Start dev server on :8000
	uv run uvicorn lintel.api.app:app --reload --port 8000

migrate: ## Run event store migrations
	uv run python -m lintel.infrastructure.event_store.migrate

all: lint typecheck test ## Run lint, typecheck, and tests
