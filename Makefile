.PHONY: help install all dev docs

include mk/tests.mk
include mk/quality.mk
include mk/server.mk
include mk/ui.mk
include mk/ollama.mk

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-extras --all-packages

all: lint typecheck test-unit test-postgres test-integration ui-build ## Run lint, typecheck, tests, and UI build

dev: ## Launch tmux dev environment (3 claude prompts + API/UI/DB)
	./scripts/dev-tmux.sh

docs: ## Build and serve documentation site (MkDocs)
	python scripts/generate_package_catalogue.py
	uv run mkdocs serve
