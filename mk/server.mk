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
