.PHONY: help install test test-contracts test-domain test-agents test-infrastructure test-workflows test-app test-unit test-postgres test-integration test-e2e test-sandbox lint typecheck format serve serve-db db-up db-down migrate all ui-install ui-dev ui-build ui-generate ui-test dev ollama-pull ollama-serve sandbox-image

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-extras --all-packages

test: ## Run all tests (pass ARGS= for extra pytest flags)
	uv run pytest $(ARGS)

test-contracts: ## Run contracts package tests
	uv run --package lintel-contracts pytest packages/contracts/tests/ -v

test-domain: ## Run domain package tests
	uv run --package lintel-domain pytest packages/domain/tests/ -v

test-agents: ## Run agents package tests
	uv run --package lintel-agents pytest packages/agents/tests/ -v

test-infrastructure: ## Run infrastructure package tests
	uv run --package lintel-infrastructure pytest packages/infrastructure/tests/ -v

test-workflows: ## Run workflows package tests
	uv run --package lintel-workflows pytest packages/workflows/tests/ -v

test-app: ## Run app package tests (in-memory only)
	uv run --package lintel pytest packages/app/tests/ -v

test-unit: ## Run unit tests (in-memory only, parallelised)
	uv run pytest packages/contracts/tests/ packages/domain/tests/ packages/agents/tests/ packages/workflows/tests/ packages/infrastructure/tests/ packages/app/tests/ -v -n auto

test-postgres: ## Run unit tests against both memory and postgres backends
	uv run pytest packages/contracts/tests/ packages/domain/tests/ packages/agents/tests/ packages/workflows/tests/ packages/infrastructure/tests/ packages/app/tests/ -v --run-postgres

test-integration: migrate ## Run integration tests (requires postgres + migrations)
	uv run pytest tests/integration -v

test-e2e: ## Run e2e tests
	uv run pytest tests/e2e -v

test-sandbox: ## Sandbox smoke + stage tests (requires Docker + sandbox image)
	uv run pytest tests/integration/sandbox -v --run-sandbox

lint: ## Check linting and formatting
	uv run ruff check packages/ tests/
	uv run ruff format --check packages/ tests/

typecheck: ## Run mypy strict type checking
	uv run mypy packages/contracts/src/lintel/contracts/ packages/domain/src/lintel/domain/ packages/agents/src/lintel/agents/ packages/infrastructure/src/lintel/infrastructure/ packages/workflows/src/lintel/workflows/ packages/app/src/lintel/

format: ## Auto-fix formatting and lint
	uv run ruff format packages/ tests/
	uv run ruff check --fix packages/ tests/

serve: ## Start dev server on :8000 (in-memory storage)
	LINTEL_STORAGE_BACKEND=memory uv run uvicorn lintel.api.app:app --reload --host 0.0.0.0 --port 8000

sandbox-image: ## Build the lintel-sandbox Docker image
	docker build -t lintel-sandbox:latest -f src/lintel/infrastructure/sandbox/Dockerfile .

db-up: ## Start PostgreSQL via docker-compose
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL..."
	@until docker compose exec postgres pg_isready -U lintel > /dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready."

db-down: ## Stop PostgreSQL
	docker compose down

serve-db: db-up migrate ## Start dev server with PostgreSQL storage
	LINTEL_STORAGE_BACKEND=postgres LINTEL_DB_DSN=postgresql://lintel:lintel@localhost:5432/lintel LITELLM_LOG=DEBUG uv run uvicorn lintel.api.app:app --reload --host 0.0.0.0 --port 8000

migrate: ## Run event store migrations
	LINTEL_DB_DSN=$${LINTEL_DB_DSN:-postgresql://lintel:lintel@localhost:5432/lintel} \
		uv run python -m lintel.infrastructure.event_store.migrate

all: lint typecheck test-unit test-postgres test-integration ui-build ## Run lint, typecheck, tests, and UI build

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

ollama-pull: ## Pull Ollama models (qwen2.5-coder:32b, llama3.1:70b)
	ollama pull qwen2.5-coder:32b
	ollama pull llama3.1:70b

ollama-serve: ollama-pull ## Pull models and start Ollama server
	ollama serve
