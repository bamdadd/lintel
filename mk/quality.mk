lint: ## Check linting and formatting
	uv run ruff check packages/ tests/
	uv run ruff format --check packages/ tests/

typecheck: ## Run mypy strict type checking
	uv run mypy \
		-p lintel.contracts \
		-p lintel.agents \
		-p lintel.workflows \
		-p lintel.api \
		-p lintel.event_store \
		-p lintel.event_bus \
		-p lintel.persistence \
		-p lintel.sandbox \
		-p lintel.pii \
		-p lintel.observability \
		-p lintel.models \
		-p lintel.slack \
		-p lintel.repos \
		-p lintel.coordination \
		-p lintel.projections \
		-p lintel.knowledge_api \
		-p lintel.kernel_policy_api \
		-p lintel.bots_api \
		-p lintel.bot_runtime \
		-p lintel.api_support \
		-p lintel.users \
		-p lintel.teams \
		-p lintel.policies_api \
		-p lintel.notifications_api \
		-p lintel.environments_api \
		-p lintel.variables_api \
		-p lintel.credentials_api \
		-p lintel.audit_api \
		-p lintel.approval_requests_api \
		-p lintel.boards \
		-p lintel.triggers_api \
		-p lintel.artifacts_api \
		-p lintel.projects_api \
		-p lintel.work_items_api \
		-p lintel.skills_api \
		-p lintel.agent_definitions_api \
		-p lintel.mcp_servers_api \
		-p lintel.ai_providers_api \
		-p lintel.models_api \
		-p lintel.repositories_api \
		-p lintel.workflow_definitions_api \
		-p lintel.settings_api \
		-p lintel.compliance_api \
		-p lintel.experimentation_api \
		-p lintel.automations \
		-p lintel.sandboxes_api \
		-p lintel.pipelines_api \
		-p lintel.chat_api \
		-p lintel.auth_api \
		-p lintel.privacy_controls_api \
		-p lintel.agent_skills_api \
		-p lintel.ai_firewall_api

format: ## Auto-fix formatting, lint, and type checking
	uv run ruff format packages/ tests/
	uv run ruff check --fix packages/ tests/
