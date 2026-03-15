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
