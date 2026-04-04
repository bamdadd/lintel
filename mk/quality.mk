lint: ## Check linting and formatting
	uv run ruff check packages/ tests/
	uv run ruff format --check packages/ tests/

typecheck: ## Run mypy strict type checking
	uv run mypy -p lintel.contracts -p lintel.agents -p lintel.workflows -p lintel.api -p lintel.event_store -p lintel.event_bus -p lintel.persistence -p lintel.sandbox -p lintel.pii -p lintel.observability -p lintel.models -p lintel.slack -p lintel.repos -p lintel.coordination -p lintel.projections -p lintel.knowledge_api -p lintel.kernel_policy_api -p lintel.bots_api -p lintel.bot_runtime

format: ## Auto-fix formatting, lint, and type checking
	uv run ruff format packages/ tests/
	uv run ruff check --fix packages/ tests/
	uv run mypy -p lintel.contracts -p lintel.agents -p lintel.workflows -p lintel.api -p lintel.event_store -p lintel.event_bus -p lintel.persistence -p lintel.sandbox -p lintel.pii -p lintel.observability -p lintel.models -p lintel.slack -p lintel.repos -p lintel.coordination -p lintel.projections -p lintel.knowledge_api -p lintel.kernel_policy_api -p lintel.bots_api -p lintel.bot_runtime
