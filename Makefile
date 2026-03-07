.PHONY: help install test test-unit test-integration test-e2e lint typecheck format serve serve-db db-up db-down migrate all ui-install ui-dev ui-build ui-generate ui-test dev

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

db-up: ## Start PostgreSQL via docker-compose
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL..."
	@until docker compose exec postgres pg_isready -U lintel > /dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready."

db-down: ## Stop PostgreSQL
	docker compose down

serve-db: db-up migrate ## Start dev server with PostgreSQL
	LINTEL_DB_DSN=postgresql://lintel:lintel@localhost:5432/lintel uv run uvicorn lintel.api.app:app --reload --port 8000

migrate: ## Run event store migrations
	LINTEL_DB_DSN=$${LINTEL_DB_DSN:-postgresql://lintel:lintel@localhost:5432/lintel} \
		uv run python -m lintel.infrastructure.event_store.migrate

all: lint typecheck test ## Run lint, typecheck, and tests

ui-install: ## Install UI dependencies
	cd ui && bun install

ui-dev: ## Start UI dev server
	cd ui && bun run dev

ui-build: ## Build UI for production
	cd ui && bun run build

ui-generate: ## Regenerate API client from OpenAPI spec
	cd ui && bun run generate:api

ui-test: ## Run UI tests
	cd ui && bun run vitest run

dev: ## Launch tmux dev environment (3 claude prompts + API/UI/DB)
	./scripts/dev-tmux.sh
