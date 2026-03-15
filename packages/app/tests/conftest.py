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

    from lintel.api.container import AppContainer
    from lintel.api.routes.agents import AgentDefinitionStore
    from lintel.api.routes.artifacts import CodeArtifactStore, TestResultStore
    from lintel.api.routes.audit import AuditEntryStore
    from lintel.api.routes.boards import BoardStore, TagStore
    from lintel.api.routes.chat import ChatStore
    from lintel.api.routes.compliance import ComplianceStore
    from lintel.api.routes.credentials import InMemoryCredentialStore
    from lintel.environments_api.store import InMemoryEnvironmentStore
    from lintel.api.routes.mcp_servers import InMemoryMCPServerStore
    from lintel.api.routes.models import InMemoryModelAssignmentStore, InMemoryModelStore
    from lintel.notifications_api.store import NotificationRuleStore
    from lintel.api.routes.pipelines import InMemoryPipelineStore
    from lintel.policies_api.store import InMemoryPolicyStore
    from lintel.api.routes.projects import ProjectStore
    from lintel.api.routes.sandboxes import SandboxStore
    from lintel.api.routes.skills import InMemorySkillStore
    from lintel.teams.store import InMemoryTeamStore
    from lintel.api.routes.triggers import InMemoryTriggerStore
    from lintel.users.store import InMemoryUserStore
    from lintel.api.routes.variables import InMemoryVariableStore
    from lintel.api.routes.work_items import WorkItemStore
    from lintel.event_store.in_memory import InMemoryEventStore
    from lintel.repos.repository_store import InMemoryRepositoryStore

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
