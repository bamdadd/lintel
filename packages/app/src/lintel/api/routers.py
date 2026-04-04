"""Router registration — mounts all API routers onto the FastAPI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.agent_definitions_api.routes import router as agent_definitions_router
from lintel.agent_metrics_api.routes import router as agent_metrics_router
from lintel.agent_skills_api.routes import router as agent_skills_router
from lintel.ai_firewall_api.routes import router as ai_firewall_router
from lintel.ai_providers_api.routes import router as ai_providers_router
from lintel.api.routes import (
    admin,
    approvals,
    debug,
    events,
    health,
    metrics,
    onboarding,
    pii,
    streams,
    sub_sessions,
    threads,
    webhooks,
    workflows,
)
from lintel.approval_requests_api.routes import router as approval_requests_router
from lintel.artifacts_api.routes import router as artifacts_router
from lintel.audit_api.routes import router as audit_router
from lintel.auth_api.mfa_routes import router as mfa_router
from lintel.auth_api.routes import router as auth_router
from lintel.auth_api.sso_routes import sso_router
from lintel.automations_api.routes import router as automations_router
from lintel.background_agents_api.routes import router as background_agents_router
from lintel.board_sync_api.routes import router as board_sync_router
from lintel.boards.routes import router as boards_router
from lintel.bot_scope_api.routes import router as bot_scope_router
from lintel.bots_api.routes import router as bots_router
from lintel.channel_adapter_registry_api.routes import (
    router as channel_adapter_registry_router,
)
from lintel.channel_connections_api.routes import router as channel_connections_router
from lintel.channel_message_routing_api.routes import router as channel_message_routing_router
from lintel.chat_api.routes import router as chat_router_routes
from lintel.chat_api.streaming import streaming_router as chat_streaming_router
from lintel.cloud_environments_api.routes import router as cloud_environments_router
from lintel.codebase_index_api.routes import router as codebase_index_router
from lintel.coding_rules_api.routes import router as coding_rules_router
from lintel.compliance_api.routes import router as compliance_router
from lintel.context_attachments_api.routes import router as context_attachments_router
from lintel.credentials_api.routes import router as credentials_router
from lintel.cross_repo_agent_api.routes import router as cross_repo_agent_router
from lintel.cross_repo_test_api.routes import router as cross_repo_test_router
from lintel.cve_remediation_api.routes import router as cve_remediation_router
from lintel.data_retention_api.routes import router as data_retention_router
from lintel.digest_api.routes import router as digest_router
from lintel.drift_detection_api.routes import router as drift_detection_router
from lintel.encryption_api.routes import router as encryption_router
from lintel.env_prebuilds_api.routes import router as env_prebuilds_router
from lintel.environments_api.routes import router as environments_router
from lintel.experimentation_api.routes import router as experimentation_router
from lintel.feedback_api.routes import router as feedback_router
from lintel.fleet_execution_api.routes import router as fleet_execution_router
from lintel.frontend_targets_api.routes import router as frontend_targets_router
from lintel.github_app_api.routes import router as github_app_router
from lintel.governance_api.routes import router as governance_router
from lintel.improvement_api.routes import router as improvement_router
from lintel.incidents_api.routes import router as incidents_router
from lintel.integration_patterns_api import router as integration_patterns_router
from lintel.jira_adapter_api.routes import router as jira_adapter_router
from lintel.kernel_policy_api.routes import router as kernel_policy_router
from lintel.knowledge_graph_api.routes import router as knowledge_graph_router
from lintel.mcp_servers_api.routes import router as mcp_servers_router
from lintel.memory_api.routes import router as memory_router
from lintel.models_api.routes import router as models_router
from lintel.multi_slack_bot_api.routes import router as multi_slack_bot_router
from lintel.multi_tenancy_api.routes import router as multi_tenancy_router
from lintel.notifications_api.routes import router as notifications_router
from lintel.notion_adapter_api.routes import router as notion_adapter_router
from lintel.org_security_api.routes import router as org_security_router
from lintel.pipeline_diagnostics_api.routes import router as pipeline_diagnostics_router
from lintel.pipelines_api.routes import router as pipelines_router
from lintel.policies_api.routes import router as policies_router
from lintel.privacy_controls_api.routes import router as privacy_controls_router
from lintel.proactive_triggers_api.routes import router as proactive_triggers_router
from lintel.process_mining_api import router as process_mining_router
from lintel.projects_api.routes import router as projects_router
from lintel.release_notes_api.routes import router as release_notes_router
from lintel.repo_auto_describe_api.routes import router as repo_auto_describe_router
from lintel.repo_description_api.routes import router as repo_description_router
from lintel.repositories_api.routes import router as repositories_router
from lintel.sandbox_credentials_api.routes import router as sandbox_credentials_router
from lintel.sandbox_pool_api.routes import router as sandbox_pool_router
from lintel.sandboxes_api.routes import router as sandboxes_router
from lintel.scheduled_tasks_api.routes import router as scheduled_tasks_router
from lintel.secret_rotation_api.routes import router as secret_rotation_router
from lintel.settings_api.channels_router import router as channels_settings_router
from lintel.settings_api.routes import router as settings_router
from lintel.skills_api.routes import router as skills_router
from lintel.slack_notifications_api.routes import router as slack_notifications_router
from lintel.slack_review_api.routes import router as slack_review_router
from lintel.slack_workflows_api.routes import router as slack_workflows_router
from lintel.stage_catalogue_api.routes import router as stage_catalogue_router
from lintel.teams.routes import router as teams_router
from lintel.telegram.webhook import router as telegram_router
from lintel.triggers_api.routes import router as triggers_router
from lintel.trust_scores_api.routes import router as trust_scores_router
from lintel.users.routes import router as users_router
from lintel.variables_api.routes import router as variables_router
from lintel.visual_verification_api.routes import router as visual_verification_router
from lintel.web_ide_api.routes import router as web_ide_router
from lintel.work_items_api.routes import router as work_items_router
from lintel.workflow_acl_api.routes import router as workflow_acl_router
from lintel.workflow_blueprints_api.routes import router as workflow_blueprints_router
from lintel.workflow_definitions_api.routes import router as workflow_definitions_router

if TYPE_CHECKING:
    from fastapi import FastAPI


def mount_routers(app: FastAPI) -> None:
    """Register all API routers on the application."""
    app.include_router(health.router, tags=["health"])
    app.include_router(threads.router, prefix="/api/v1", tags=["threads"])
    app.include_router(repositories_router, prefix="/api/v1", tags=["repositories"])
    app.include_router(workflows.router, prefix="/api/v1", tags=["workflows"])
    app.include_router(agent_definitions_router, prefix="/api/v1", tags=["agents"])
    app.include_router(background_agents_router, prefix="/api/v1", tags=["agents"])
    app.include_router(agent_metrics_router, prefix="/api/v1", tags=["agent-metrics"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["approvals"])
    app.include_router(sandboxes_router, prefix="/api/v1", tags=["sandboxes"])
    app.include_router(skills_router, prefix="/api/v1", tags=["skills"])
    app.include_router(streams.router, prefix="/api/v1", tags=["streams"])
    app.include_router(events.router, prefix="/api/v1", tags=["events"])
    app.include_router(pii.router, prefix="/api/v1", tags=["pii"])
    app.include_router(settings_router, prefix="/api/v1", tags=["settings"])
    app.include_router(workflow_definitions_router, prefix="/api/v1", tags=["workflow-definitions"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
    app.include_router(credentials_router, prefix="/api/v1", tags=["credentials"])
    app.include_router(digest_router, prefix="/api/v1", tags=["digests"])
    app.include_router(ai_providers_router, prefix="/api/v1", tags=["ai-providers"])
    app.include_router(projects_router, prefix="/api/v1", tags=["projects"])
    app.include_router(work_items_router, prefix="/api/v1", tags=["work-items"])
    app.include_router(
        pipeline_diagnostics_router,
        prefix="/api/v1",
        tags=["pipeline-diagnostics"],
    )
    app.include_router(pipelines_router, prefix="/api/v1", tags=["pipelines"])
    app.include_router(environments_router, prefix="/api/v1", tags=["environments"])
    app.include_router(env_prebuilds_router, prefix="/api/v1", tags=["env-prebuilds"])
    app.include_router(triggers_router, prefix="/api/v1", tags=["triggers"])
    app.include_router(cross_repo_test_router, prefix="/api/v1", tags=["cross-repo-tests"])
    app.include_router(automations_router, prefix="/api/v1", tags=["automations"])
    app.include_router(variables_router, prefix="/api/v1", tags=["variables"])
    app.include_router(users_router, prefix="/api/v1", tags=["users"])
    app.include_router(teams_router, prefix="/api/v1", tags=["teams"])
    app.include_router(policies_router, prefix="/api/v1", tags=["policies"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["notifications"])
    app.include_router(audit_router, prefix="/api/v1", tags=["audit"])
    app.include_router(artifacts_router, prefix="/api/v1", tags=["artifacts"])
    app.include_router(approval_requests_router, prefix="/api/v1", tags=["approval-requests"])
    app.include_router(chat_router_routes, prefix="/api/v1", tags=["chat"])
    app.include_router(chat_streaming_router, prefix="/api/v1", tags=["chat"])
    app.include_router(models_router, prefix="/api/v1", tags=["models"])
    app.include_router(mcp_servers_router, prefix="/api/v1", tags=["mcp-servers"])
    app.include_router(onboarding.router, prefix="/api/v1", tags=["onboarding"])
    app.include_router(org_security_router, prefix="/api/v1", tags=["org-security"])
    app.include_router(boards_router, prefix="/api/v1", tags=["boards"])
    app.include_router(bots_router, prefix="/api/v1", tags=["bots"])
    app.include_router(board_sync_router, prefix="/api/v1", tags=["board-sync"])
    app.include_router(cloud_environments_router, prefix="/api/v1", tags=["cloud-environments"])
    app.include_router(compliance_router, prefix="/api/v1", tags=["compliance"])
    app.include_router(drift_detection_router, prefix="/api/v1", tags=["drift-detection"])
    app.include_router(experimentation_router, prefix="/api/v1", tags=["experimentation"])
    app.include_router(feedback_router, prefix="/api/v1", tags=["feedback"])
    app.include_router(governance_router, prefix="/api/v1", tags=["governance"])
    app.include_router(kernel_policy_router, prefix="/api/v1", tags=["kernel-policies"])
    app.include_router(improvement_router, prefix="/api/v1", tags=["improvement"])
    app.include_router(memory_router, prefix="/api/v1", tags=["memory"])
    app.include_router(integration_patterns_router, prefix="/api/v1", tags=["integration-patterns"])
    app.include_router(process_mining_router, prefix="/api/v1", tags=["process-mining"])
    app.include_router(stage_catalogue_router, prefix="/api/v1", tags=["stage-catalogue"])
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(debug.router, prefix="/api/v1", tags=["debug"])
    app.include_router(telegram_router, prefix="/api/v1", tags=["telegram"])
    app.include_router(channels_settings_router, prefix="/api/v1", tags=["channels"])
    app.include_router(
        channel_adapter_registry_router,
        prefix="/api/v1",
        tags=["channel-adapters"],
    )
    app.include_router(
        channel_connections_router,
        prefix="/api/v1",
        tags=["channel-connections"],
    )
    app.include_router(
        channel_message_routing_router,
        prefix="/api/v1",
        tags=["channel-routing"],
    )
    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
    app.include_router(sso_router, prefix="/api/v1", tags=["auth"])
    app.include_router(mfa_router, prefix="/api/v1", tags=["auth"])
    app.include_router(codebase_index_router, prefix="/api/v1", tags=["codebase-index"])
    app.include_router(trust_scores_router, prefix="/api/v1", tags=["trust-scores"])
    app.include_router(privacy_controls_router, prefix="/api/v1", tags=["privacy-controls"])
    app.include_router(agent_skills_router, prefix="/api/v1", tags=["agent-skills"])
    app.include_router(
        context_attachments_router,
        prefix="/api/v1",
        tags=["context-attachments"],
    )
    app.include_router(ai_firewall_router, prefix="/api/v1", tags=["ai-firewall"])
    app.include_router(
        slack_notifications_router,
        prefix="/api/v1",
        tags=["slack-notifications"],
    )
    app.include_router(slack_review_router, prefix="/api/v1", tags=["slack-review"])
    app.include_router(slack_workflows_router, prefix="/api/v1", tags=["slack-workflows"])
    app.include_router(coding_rules_router, prefix="/api/v1", tags=["coding-rules"])
    app.include_router(sandbox_pool_router, prefix="/api/v1", tags=["sandbox-pool"])
    app.include_router(scheduled_tasks_router, prefix="/api/v1", tags=["scheduled-tasks"])
    app.include_router(
        sandbox_credentials_router,
        prefix="/api/v1",
        tags=["sandbox-credentials"],
    )
    app.include_router(
        workflow_blueprints_router,
        prefix="/api/v1",
        tags=["workflow-blueprints"],
    )
    app.include_router(release_notes_router, prefix="/api/v1", tags=["release-notes"])
    app.include_router(
        visual_verification_router,
        prefix="/api/v1",
        tags=["visual-verification"],
    )
    app.include_router(cross_repo_agent_router, prefix="/api/v1", tags=["cross-repo"])
    app.include_router(cve_remediation_router, prefix="/api/v1", tags=["cve-remediation"])
    app.include_router(data_retention_router, prefix="/api/v1", tags=["data-retention"])
    app.include_router(
        secret_rotation_router,
        prefix="/api/v1",
        tags=["secret-rotation"],
    )
    app.include_router(github_app_router, prefix="/api/v1", tags=["github-app"])
    app.include_router(jira_adapter_router, prefix="/api/v1", tags=["jira-adapter"])
    app.include_router(notion_adapter_router, prefix="/api/v1", tags=["notion-adapter"])
    app.include_router(web_ide_router, prefix="/api/v1", tags=["web-ide"])
    app.include_router(encryption_router, prefix="/api/v1", tags=["encryption"])
    app.include_router(multi_slack_bot_router, prefix="/api/v1", tags=["slack-bots"])
    app.include_router(multi_tenancy_router, prefix="/api/v1", tags=["multi-tenancy"])
    app.include_router(incidents_router, prefix="/api/v1", tags=["incidents"])
    app.include_router(
        proactive_triggers_router,
        prefix="/api/v1",
        tags=["proactive-triggers"],
    )
    app.include_router(bot_scope_router, prefix="/api/v1", tags=["bot-scopes"])
    app.include_router(
        fleet_execution_router,
        prefix="/api/v1",
        tags=["fleet-execution"],
    )
    app.include_router(knowledge_graph_router, prefix="/api/v1", tags=["knowledge-graph"])
    app.include_router(
        repo_description_router,
        prefix="/api/v1",
        tags=["repo-descriptions"],
    )
    app.include_router(sub_sessions.router, prefix="/api/v1", tags=["sub-sessions"])
    app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
    app.include_router(
        frontend_targets_router,
        prefix="/api/v1",
        tags=["frontend-targets"],
    )
    app.include_router(workflow_acl_router, prefix="/api/v1", tags=["workflow-acl"])
    app.include_router(
        repo_auto_describe_router,
        prefix="/api/v1",
        tags=["repo-auto-describe"],
    )
