"""Root test configuration for the app package.

Provides a container fixture that wires up an in-memory AppContainer
suitable for unit tests that need DI-provided stores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from lintel.api.container import AppContainer as AppContainerType


@pytest.fixture
def container() -> Generator[AppContainerType]:
    """Provide a wired in-memory AppContainer for unit tests.

    Wires the container so ``Provide[AppContainer.X]`` can be resolved in
    route handlers decorated with ``@inject``.  Call ``container.X.override``
    to inject test doubles for specific stores.
    """
    from dependency_injector import providers

    from lintel.agent_definitions_api.store import AgentDefinitionStore
    from lintel.api.container import AppContainer
    from lintel.chat_api.routes import ChatStore
    from lintel.compliance_api.store import ComplianceStore
    from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore
    from lintel.pipelines_api.routes import InMemoryPipelineStore
    from lintel.sandboxes_api.routes import SandboxStore
    from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
    from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore
    from lintel.audit_api.store import AuditEntryStore
    from lintel.boards.store import BoardStore, TagStore
    from lintel.credentials_api.store import InMemoryCredentialStore
    from lintel.environments_api.store import InMemoryEnvironmentStore
    from lintel.event_store.in_memory import InMemoryEventStore
    from lintel.mcp_servers_api.store import InMemoryMCPServerStore
    from lintel.notifications_api.store import NotificationRuleStore
    from lintel.policies_api.store import InMemoryPolicyStore
    from lintel.projects_api.store import ProjectStore
    from lintel.repos.repository_store import InMemoryRepositoryStore
    from lintel.skills_api.store import InMemorySkillStore
    from lintel.teams.store import InMemoryTeamStore
    from lintel.triggers_api.store import InMemoryTriggerStore
    from lintel.users.store import InMemoryUserStore
    from lintel.variables_api.store import InMemoryVariableStore
    from lintel.work_items_api.store import WorkItemStore

    c = AppContainer()

    stores: dict[str, object] = {
        "event_store": InMemoryEventStore(),
        "repository_store": InMemoryRepositoryStore(),
        "skill_store": InMemorySkillStore(),
        "credential_store": InMemoryCredentialStore(),
        "project_store": ProjectStore(),
        "work_item_store": WorkItemStore(),
        "pipeline_store": InMemoryPipelineStore(),
        "environment_store": InMemoryEnvironmentStore(),
        "trigger_store": InMemoryTriggerStore(),
        "variable_store": InMemoryVariableStore(),
        "user_store": InMemoryUserStore(),
        "team_store": InMemoryTeamStore(),
        "policy_store": InMemoryPolicyStore(),
        "notification_rule_store": NotificationRuleStore(),
        "audit_entry_store": AuditEntryStore(),
        "code_artifact_store": CodeArtifactStore(),
        "test_result_store": TestResultStore(),
        "approval_request_store": InMemoryApprovalRequestStore(),
        "chat_store": ChatStore(),
        "agent_definition_store": AgentDefinitionStore(),
        "model_store": InMemoryModelStore(),
        "model_assignment_store": InMemoryModelAssignmentStore(),
        "mcp_server_store": InMemoryMCPServerStore(),
        "sandbox_store": SandboxStore(),
        "tag_store": TagStore(),
        "board_store": BoardStore(),
        "regulation_store": ComplianceStore("regulation_id"),
        "compliance_policy_store": ComplianceStore("policy_id"),
        "procedure_store": ComplianceStore("procedure_id"),
        "practice_store": ComplianceStore("practice_id"),
        "strategy_store": ComplianceStore("strategy_id"),
        "kpi_store": ComplianceStore("kpi_id"),
        "experiment_store": ComplianceStore("experiment_id"),
        "compliance_metric_store": ComplianceStore("metric_id"),
        "knowledge_entry_store": ComplianceStore("entry_id"),
        "knowledge_extraction_store": ComplianceStore("run_id"),
        "architecture_decision_store": ComplianceStore("decision_id"),
    }

    for name, instance in stores.items():
        provider: providers.Provider[object] | None = getattr(c, name, None)
        if provider is not None:
            provider.override(providers.Object(instance))

    c.wire(packages=["lintel.api.routes"], modules=["lintel.api.deps"])
    yield c
    c.unwire()
