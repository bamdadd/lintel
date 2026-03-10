.PHONY: test test-unit

test: ## Run all tests
	uv run pytest -v

test-unit: ## Run unit tests (parallelised)
	uv run pytest tests/ -v -n auto
