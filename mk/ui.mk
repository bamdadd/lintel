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
