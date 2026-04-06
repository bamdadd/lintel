lint: ## Check linting and formatting
	uv run ruff check packages/ tests/
	uv run ruff format --check packages/ tests/

# All packages that have src/lintel/<namespace>/ directories.
# Keep sorted alphabetically for easy maintenance.
MYPY_PACKAGES = \
	-p lintel.agents \
	-p lintel.agent_definitions_api \
	-p lintel.agent_metrics_api \
	-p lintel.agent_skills_api \
	-p lintel.ai_firewall_api \
	-p lintel.ai_providers_api \
	-p lintel.api \
	-p lintel.api_support \
	-p lintel.approval_requests_api \
	-p lintel.artifacts_api \
	-p lintel.audit_api \
	-p lintel.auth_api \
	-p lintel.automations \
	-p lintel.background_agents_api \
	-p lintel.board_sync_api \
	-p lintel.boards \
	-p lintel.bot_runtime \
	-p lintel.bot_scope_api \
	-p lintel.bots_api \
	-p lintel.browser_extension_api \
	-p lintel.channel_adapter_registry_api \
	-p lintel.channel_connections_api \
	-p lintel.channel_message_routing_api \
	-p lintel.channels \
	-p lintel.chat_api \
	-p lintel.cloud_environments_api \
	-p lintel.cloud_providers_api \
	-p lintel.codebase_index_api \
	-p lintel.coding_rules_api \
	-p lintel.compliance_api \
	-p lintel.context_attachments_api \
	-p lintel.context_injection \
	-p lintel.contracts \
	-p lintel.coordination \
	-p lintel.credentials_api \
	-p lintel.cross_repo_agent_api \
	-p lintel.cross_repo_test_api \
	-p lintel.cve_remediation_api \
	-p lintel.data_retention_api \
	-p lintel.digest_api \
	-p lintel.domain \
	-p lintel.drift_detection_api \
	-p lintel.encryption_api \
	-p lintel.env_prebuilds_api \
	-p lintel.environments_api \
	-p lintel.event_bus \
	-p lintel.event_store \
	-p lintel.experimentation_api \
	-p lintel.feedback_api \
	-p lintel.fleet_execution_api \
	-p lintel.frontend_targets_api \
	-p lintel.github_app_api \
	-p lintel.governance_api \
	-p lintel.improvement_api \
	-p lintel.incidents_api \
	-p lintel.integration_patterns_api \
	-p lintel.jira_adapter_api \
	-p lintel.kernel_policy_api \
	-p lintel.knowledge_api \
	-p lintel.knowledge_graph_api \
	-p lintel.mcp_servers_api \
	-p lintel.memory \
	-p lintel.memory_api \
	-p lintel.models \
	-p lintel.models_api \
	-p lintel.multi_slack_bot_api \
	-p lintel.multi_telegram_bot_api \
	-p lintel.multi_tenancy_api \
	-p lintel.multiplayer_sessions_api \
	-p lintel.notifications_api \
	-p lintel.notion_adapter_api \
	-p lintel.observability \
	-p lintel.org_security_api \
	-p lintel.persistence \
	-p lintel.pii \
	-p lintel.pipeline_diagnostics_api \
	-p lintel.pipelines_api \
	-p lintel.policies_api \
	-p lintel.privacy_controls_api \
	-p lintel.proactive_triggers_api \
	-p lintel.process_mining_api \
	-p lintel.projections \
	-p lintel.projects_api \
	-p lintel.release_notes_api \
	-p lintel.repo_auto_describe_api \
	-p lintel.repo_description_api \
	-p lintel.repos \
	-p lintel.repositories_api \
	-p lintel.sandbox \
	-p lintel.sandbox_credentials_api \
	-p lintel.sandbox_pool_api \
	-p lintel.sandboxes_api \
	-p lintel.scheduled_tasks_api \
	-p lintel.secret_rotation_api \
	-p lintel.settings_api \
	-p lintel.skills_api \
	-p lintel.slack \
	-p lintel.slack_notifications_api \
	-p lintel.slack_review_api \
	-p lintel.slack_workflows_api \
	-p lintel.stage_catalogue_api \
	-p lintel.teams \
	-p lintel.tech_spec_api \
	-p lintel.telegram \
	-p lintel.triggers_api \
	-p lintel.trust_scores_api \
	-p lintel.users \
	-p lintel.variables_api \
	-p lintel.visual_verification_api \
	-p lintel.web_ide_api \
	-p lintel.work_items_api \
	-p lintel.workflow_acl_api \
	-p lintel.workflow_blueprints_api \
	-p lintel.workflow_definitions_api \
	-p lintel.workflows

typecheck: ## Run mypy strict type checking
	uv run mypy $(MYPY_PACKAGES)

format: ## Auto-fix formatting, lint, and type checking
	uv run ruff format packages/ tests/
	uv run ruff check --fix packages/ tests/
	uv run mypy $(MYPY_PACKAGES)
