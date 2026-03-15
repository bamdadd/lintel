.PHONY: help install test test-affected test-contracts test-agents test-workflows test-app test-event-store test-event-bus test-persistence test-sandbox test-pii test-observability test-models test-slack test-repos test-coordination test-projections test-api-support test-users test-teams test-policies-api test-notifications-api test-environments-api test-variables-api test-credentials-api test-audit-api test-approval-requests-api test-boards test-triggers-api test-artifacts-api test-projects-api test-work-items-api test-skills-api test-agent-definitions-api test-mcp-servers-api test-models-api test-ai-providers-api test-repositories-api test-workflow-definitions-api test-settings-api test-compliance-api test-experimentation-api test-automations-api test-sandboxes-api test-pipelines-api test-chat-api test-unit test-postgres test-integration test-e2e lint typecheck format serve serve-db db-up db-down migrate all ui-install ui-dev ui-build ui-generate ui-test dev ollama-pull ollama-serve sandbox-image

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-extras --all-packages

test: ## Run all tests (pass ARGS= for extra pytest flags)
	uv run pytest $(ARGS)

test-affected: ## Run tests only for packages affected since BASE_REF (default: origin/main)
	@AFFECTED=$$(./scripts/affected-packages.sh $(BASE_REF)); \
	echo "Affected packages: $$AFFECTED"; \
	for pkg in $$AFFECTED; do \
		dir=$$(echo $$pkg | sed 's/^lintel-//;s/^lintel$$/app/'); \
		echo "--- Testing $$pkg (packages/$$dir/tests/) ---"; \
		uv run pytest packages/$$dir/tests/ -v || exit 1; \
	done

test-contracts: ## Run contracts package tests
	uv run --package lintel-contracts pytest packages/contracts/tests/ -v

test-agents: ## Run agents package tests
	uv run --package lintel-agents pytest packages/agents/tests/ -v

test-workflows: ## Run workflows package tests
	uv run --package lintel-workflows pytest packages/workflows/tests/ -v

test-app: ## Run app package tests (in-memory only)
	uv run --package lintel pytest packages/app/tests/ -v

test-event-store: ## Run event-store package tests
	uv run pytest packages/event-store/tests/ -v

test-event-bus: ## Run event-bus package tests
	uv run pytest packages/event-bus/tests/ -v

test-persistence: ## Run persistence package tests
	uv run pytest packages/persistence/tests/ -v

test-pii: ## Run PII package tests
	uv run pytest packages/pii/tests/ -v

test-observability: ## Run observability package tests
	uv run pytest packages/observability/tests/ -v

test-models: ## Run models package tests
	uv run pytest packages/models/tests/ -v

test-slack: ## Run slack package tests
	uv run pytest packages/slack/tests/ -v

test-repos: ## Run repos package tests
	uv run pytest packages/repos/tests/ -v

test-coordination: ## Run coordination package tests
	uv run pytest packages/coordination/tests/ -v

test-projections: ## Run projections package tests
	uv run pytest packages/projections/tests/ -v

test-api-support: ## Run api-support package tests
	uv run pytest packages/api-support/tests/ -v

test-users: ## Run users package tests
	uv run pytest packages/users/tests/ -v

test-teams: ## Run teams package tests
	uv run pytest packages/teams/tests/ -v

test-policies-api: ## Run policies-api package tests
	uv run pytest packages/policies-api/tests/ -v

test-notifications-api: ## Run notifications-api package tests
	uv run pytest packages/notifications-api/tests/ -v

test-environments-api: ## Run environments-api package tests
	uv run pytest packages/environments-api/tests/ -v

test-variables-api: ## Run variables-api package tests
	uv run pytest packages/variables-api/tests/ -v

test-credentials-api: ## Run credentials-api package tests
	uv run pytest packages/credentials-api/tests/ -v

test-audit-api: ## Run audit-api package tests
	uv run pytest packages/audit-api/tests/ -v

test-approval-requests-api: ## Run approval-requests-api package tests
	uv run pytest packages/approval-requests-api/tests/ -v

test-boards: ## Run boards package tests
	uv run pytest packages/boards/tests/ -v

test-triggers-api: ## Run triggers-api package tests
	uv run pytest packages/triggers-api/tests/ -v

test-artifacts-api: ## Run artifacts-api package tests
	uv run pytest packages/artifacts-api/tests/ -v

test-projects-api: ## Run projects-api package tests
	uv run pytest packages/projects-api/tests/ -v

test-work-items-api: ## Run work-items-api package tests
	uv run pytest packages/work-items-api/tests/ -v

test-skills-api: ## Run skills-api package tests
	uv run pytest packages/skills-api/tests/ -v

test-agent-definitions-api: ## Run agent-definitions-api package tests
	uv run pytest packages/agent-definitions-api/tests/ -v

test-mcp-servers-api: ## Run mcp-servers-api package tests
	uv run pytest packages/mcp-servers-api/tests/ -v

test-models-api: ## Run models-api package tests
	uv run pytest packages/models-api/tests/ -v

test-ai-providers-api: ## Run ai-providers-api package tests
	uv run pytest packages/ai-providers-api/tests/ -v

test-repositories-api: ## Run repositories-api package tests
	uv run pytest packages/repositories-api/tests/ -v

test-workflow-definitions-api: ## Run workflow-definitions-api package tests
	uv run pytest packages/workflow-definitions-api/tests/ -v

test-settings-api: ## Run settings-api package tests
	uv run pytest packages/settings-api/tests/ -v

test-compliance-api: ## Run compliance-api package tests
	uv run pytest packages/compliance-api/tests/ -v

test-experimentation-api: ## Run experimentation-api package tests
	uv run pytest packages/experimentation-api/tests/ -v

test-automations-api: ## Run automations-api package tests
	uv run pytest packages/automations-api/tests/ -v

test-sandboxes-api: ## Run sandboxes-api package tests
	uv run pytest packages/sandboxes-api/tests/ -v

test-pipelines-api: ## Run pipelines-api package tests
	uv run pytest packages/pipelines-api/tests/ -v

test-chat-api: ## Run chat-api package tests
	uv run pytest packages/chat-api/tests/ -v

test-unit: ## Run unit tests (in-memory only, parallelised)
	uv run pytest packages/contracts/tests/ packages/agents/tests/ packages/workflows/tests/ packages/app/tests/ packages/event-store/tests/ packages/event-bus/tests/ packages/persistence/tests/ packages/sandbox/tests/ packages/pii/tests/ packages/observability/tests/ packages/models/tests/ packages/slack/tests/ packages/repos/tests/ packages/coordination/tests/ packages/projections/tests/ packages/api-support/tests/ packages/users/tests/ packages/teams/tests/ packages/policies-api/tests/ packages/notifications-api/tests/ packages/environments-api/tests/ packages/variables-api/tests/ packages/credentials-api/tests/ packages/audit-api/tests/ packages/approval-requests-api/tests/ packages/boards/tests/ packages/triggers-api/tests/ packages/artifacts-api/tests/ packages/projects-api/tests/ packages/work-items-api/tests/ packages/skills-api/tests/ packages/agent-definitions-api/tests/ packages/mcp-servers-api/tests/ packages/models-api/tests/ packages/ai-providers-api/tests/ packages/repositories-api/tests/ packages/workflow-definitions-api/tests/ packages/settings-api/tests/ packages/compliance-api/tests/ packages/experimentation-api/tests/ packages/automations-api/tests/ packages/sandboxes-api/tests/ packages/pipelines-api/tests/ packages/chat-api/tests/ -v -n auto

test-postgres: ## Run unit tests against both memory and postgres backends
	uv run pytest packages/contracts/tests/ packages/agents/tests/ packages/workflows/tests/ packages/app/tests/ packages/event-store/tests/ packages/event-bus/tests/ packages/persistence/tests/ packages/sandbox/tests/ packages/pii/tests/ packages/observability/tests/ packages/models/tests/ packages/slack/tests/ packages/repos/tests/ packages/coordination/tests/ packages/projections/tests/ packages/api-support/tests/ packages/users/tests/ packages/teams/tests/ packages/policies-api/tests/ packages/notifications-api/tests/ packages/environments-api/tests/ packages/variables-api/tests/ packages/credentials-api/tests/ packages/audit-api/tests/ packages/approval-requests-api/tests/ packages/boards/tests/ packages/triggers-api/tests/ packages/artifacts-api/tests/ packages/projects-api/tests/ packages/work-items-api/tests/ packages/skills-api/tests/ packages/agent-definitions-api/tests/ packages/mcp-servers-api/tests/ packages/models-api/tests/ packages/ai-providers-api/tests/ packages/repositories-api/tests/ packages/workflow-definitions-api/tests/ packages/settings-api/tests/ packages/compliance-api/tests/ packages/experimentation-api/tests/ packages/automations-api/tests/ packages/sandboxes-api/tests/ packages/pipelines-api/tests/ packages/chat-api/tests/ -v --run-postgres

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
	uv run mypy -p lintel.contracts -p lintel.agents -p lintel.workflows -p lintel.api -p lintel.event_store -p lintel.event_bus -p lintel.persistence -p lintel.sandbox -p lintel.pii -p lintel.observability -p lintel.models -p lintel.slack -p lintel.repos -p lintel.coordination -p lintel.projections

format: ## Auto-fix formatting, lint, and type checking
	uv run ruff format packages/ tests/
	uv run ruff check --fix packages/ tests/
	uv run mypy -p lintel.contracts -p lintel.agents -p lintel.workflows -p lintel.api -p lintel.event_store -p lintel.event_bus -p lintel.persistence -p lintel.sandbox -p lintel.pii -p lintel.observability -p lintel.models -p lintel.slack -p lintel.repos -p lintel.coordination -p lintel.projections

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
	LINTEL_STORAGE_BACKEND=postgres LINTEL_DB_DSN=postgresql://lintel:lintel@localhost:5432/lintel LITELLM_LOG=DEBUG uv run uvicorn lintel.api.app:app --reload --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 2

migrate: ## Run event store migrations
	LINTEL_DB_DSN=$${LINTEL_DB_DSN:-postgresql://lintel:lintel@localhost:5432/lintel} \
		uv run python -m lintel.event_store.migrate

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
