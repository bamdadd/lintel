# Package Catalogue

Lintel is a uv workspace monorepo with **79 packages** under `packages/`.
This page is auto-generated from `pyproject.toml` files.

!!! info "Regenerate this page"
    Run `python scripts/generate_package_catalogue.py` to update.

## Core packages (5)

| Package | Name | Lintel dependencies |
|---------|------|---------------------|
| `packages/agents/` | `lintel-agents` | lintel-contracts, lintel-models, lintel-sandbox |
| `packages/app/` | `lintel` | lintel-agent-definitions-api, lintel-agent-skills-api, lintel-agents, lintel-ai-firewall-api, lintel-ai-providers-api, lintel-api-support, lintel-approval-requests-api, lintel-artifacts-api, lintel-audit-api, lintel-auth-api, lintel-automations-api, lintel-boards, lintel-channel-connections-api, lintel-channels, lintel-chat-api, lintel-codebase-index-api, lintel-coding-rules-api, lintel-compliance-api, lintel-context-attachments-api, lintel-contracts, lintel-coordination, lintel-credentials-api, lintel-digest-api, lintel-domain, lintel-drift-detection-api, lintel-environments-api, lintel-event-bus, lintel-event-store, lintel-experimentation-api, lintel-feedback-api, lintel-governance-api, lintel-improvement-api, lintel-infrastructure, lintel-integration-patterns-api, lintel-mcp-servers-api, lintel-memory, lintel-memory-api, lintel-models, lintel-models-api, lintel-notifications-api, lintel-observability, lintel-persistence, lintel-pii, lintel-pipelines-api, lintel-policies-api, lintel-privacy-controls-api, lintel-process-mining-api, lintel-projections, lintel-projects-api, lintel-release-notes-api, lintel-repos, lintel-repositories-api, lintel-sandbox, lintel-sandbox-credentials-api, lintel-sandbox-pool-api, lintel-sandboxes-api, lintel-scheduled-tasks-api, lintel-settings-api, lintel-skills-api, lintel-slack, lintel-slack-notifications-api, lintel-slack-workflows-api, lintel-stage-catalogue-api, lintel-teams, lintel-telegram, lintel-triggers-api, lintel-trust-scores-api, lintel-users, lintel-variables-api, lintel-visual-verification-api, lintel-work-items-api, lintel-workflow-blueprints-api, lintel-workflow-definitions-api, lintel-workflows |
| `packages/contracts/` | `lintel-contracts` | — |
| `packages/domain/` | `lintel-domain` | lintel-contracts, lintel-models, lintel-observability, lintel-sandbox |
| `packages/workflows/` | `lintel-workflows` | lintel-agents, lintel-context-injection, lintel-contracts, lintel-domain, lintel-observability, lintel-repos, lintel-sandbox |

## Library packages (17)

| Package | Name | Lintel dependencies |
|---------|------|---------------------|
| `packages/api-support/` | `lintel-api-support` | lintel-contracts |
| `packages/channels/` | `lintel-channels` | lintel-contracts |
| `packages/context-injection/` | `lintel-context-injection` | lintel-contracts, lintel-domain |
| `packages/coordination/` | `lintel-coordination` | — |
| `packages/event-bus/` | `lintel-event-bus` | lintel-contracts |
| `packages/event-store/` | `lintel-event-store` | lintel-contracts |
| `packages/infrastructure/` | `lintel-infrastructure` | lintel-contracts |
| `packages/memory/` | `lintel-memory` | lintel-contracts |
| `packages/models/` | `lintel-models` | lintel-contracts, lintel-sandbox |
| `packages/observability/` | `lintel-observability` | lintel-contracts |
| `packages/persistence/` | `lintel-persistence` | lintel-contracts, lintel-models, lintel-repos |
| `packages/pii/` | `lintel-pii` | lintel-contracts |
| `packages/projections/` | `lintel-projections` | lintel-contracts, lintel-event-bus |
| `packages/repos/` | `lintel-repos` | lintel-contracts |
| `packages/sandbox/` | `lintel-sandbox` | lintel-contracts |
| `packages/slack/` | `lintel-slack` | lintel-channels, lintel-contracts |
| `packages/telegram/` | `lintel-telegram` | lintel-channels, lintel-contracts |

## API packages (57)

| Package | Name | Lintel dependencies |
|---------|------|---------------------|
| `packages/agent-definitions-api/` | `lintel-agent-definitions-api` | lintel-agents, lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence |
| `packages/agent-skills-api/` | `lintel-agent-skills-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/ai-firewall-api/` | `lintel-ai-firewall-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/ai-providers-api/` | `lintel-ai-providers-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-models, lintel-persistence |
| `packages/approval-requests-api/` | `lintel-approval-requests-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/artifacts-api/` | `lintel-artifacts-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/audit-api/` | `lintel-audit-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/auth-api/` | `lintel-auth-api` | lintel-api-support, lintel-domain |
| `packages/automations-api/` | `lintel-automations-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-workflows |
| `packages/boards/` | `lintel-boards` | lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence, lintel-work-items-api |
| `packages/channel-connections-api/` | `lintel-channel-connections-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/chat-api/` | `lintel-chat-api` | lintel-agents, lintel-api-support, lintel-contracts, lintel-domain, lintel-event-bus, lintel-event-store, lintel-mcp-servers-api, lintel-models, lintel-persistence, lintel-pipelines-api, lintel-workflows |
| `packages/codebase-index-api/` | `lintel-codebase-index-api` | lintel-api-support, lintel-compliance-api, lintel-contracts, lintel-domain |
| `packages/coding-rules-api/` | `lintel-coding-rules-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/compliance-api/` | `lintel-compliance-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/context-attachments-api/` | `lintel-context-attachments-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/credentials-api/` | `lintel-credentials-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence |
| `packages/digest-api/` | `lintel-digest-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/drift-detection-api/` | `lintel-drift-detection-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/environments-api/` | `lintel-environments-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/experimentation-api/` | `lintel-experimentation-api` | lintel-api-support, lintel-compliance-api, lintel-contracts, lintel-domain |
| `packages/feedback-api/` | `lintel-feedback-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/governance-api/` | `lintel-governance-api` | lintel-api-support, lintel-compliance-api, lintel-contracts, lintel-domain |
| `packages/improvement-api/` | `lintel-improvement-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-workflows |
| `packages/integration-patterns-api/` | `lintel-integration-patterns-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/knowledge-api/` | `lintel-knowledge-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/mcp-servers-api/` | `lintel-mcp-servers-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/memory-api/` | `lintel-memory-api` | lintel-api-support, lintel-contracts, lintel-memory |
| `packages/models-api/` | `lintel-models-api` | lintel-ai-providers-api, lintel-api-support, lintel-contracts, lintel-models |
| `packages/notifications-api/` | `lintel-notifications-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/pipelines-api/` | `lintel-pipelines-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-event-bus, lintel-persistence, lintel-workflows |
| `packages/policies-api/` | `lintel-policies-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/privacy-controls-api/` | `lintel-privacy-controls-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/process-mining-api/` | `lintel-process-mining-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/projects-api/` | `lintel-projects-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence |
| `packages/release-notes-api/` | `lintel-release-notes-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/repositories-api/` | `lintel-repositories-api` | lintel-api-support, lintel-contracts, lintel-repos |
| `packages/sandbox-credentials-api/` | `lintel-sandbox-credentials-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/sandbox-pool-api/` | `lintel-sandbox-pool-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/sandboxes-api/` | `lintel-sandboxes-api` | lintel-api-support, lintel-contracts, lintel-persistence, lintel-sandbox |
| `packages/scheduled-tasks-api/` | `lintel-scheduled-tasks-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/settings-api/` | `lintel-settings-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence |
| `packages/skills-api/` | `lintel-skills-api` | lintel-agents, lintel-api-support, lintel-contracts, lintel-domain |
| `packages/slack-notifications-api/` | `lintel-slack-notifications-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/slack-workflows-api/` | `lintel-slack-workflows-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/stage-catalogue-api/` | `lintel-stage-catalogue-api` | lintel-workflows |
| `packages/teams/` | `lintel-teams` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/tech-spec-api/` | `lintel-tech-spec-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/test-plan-api/` | `lintel-test-plan-api` | lintel-api-support |
| `packages/triggers-api/` | `lintel-triggers-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/trust-scores-api/` | `lintel-trust-scores-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/users/` | `lintel-users` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/variables-api/` | `lintel-variables-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/visual-verification-api/` | `lintel-visual-verification-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/work-items-api/` | `lintel-work-items-api` | lintel-api-support, lintel-contracts, lintel-domain, lintel-persistence, lintel-workflows |
| `packages/workflow-blueprints-api/` | `lintel-workflow-blueprints-api` | lintel-api-support, lintel-contracts, lintel-domain |
| `packages/workflow-definitions-api/` | `lintel-workflow-definitions-api` | lintel-api-support, lintel-contracts, lintel-workflows |
