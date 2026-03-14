"""DI container for the Lintel application.

Uses ``dependency_injector`` declarative container. Stores are registered as
``providers.Object`` holders so the lifespan can inject already-constructed
instances (both in-memory and Postgres variants) without duplicating
construction logic.

Usage in lifespan::

    container = AppContainer()
    container.wire()
    container.chat_store.override(providers.Object(my_chat_store))

Usage in route handlers::

    from dependency_injector.wiring import inject, Provide
    from lintel.api.container import AppContainer

    @router.get("/conversations")
    @inject
    async def list_conversations(
        store: ChatStore = Depends(Provide[AppContainer.chat_store]),
    ) -> list[dict[str, Any]]:
        ...
"""

from __future__ import annotations

from typing import Any

from dependency_injector import containers, providers


class AppContainer(containers.DeclarativeContainer):
    """Root DI container for the Lintel application."""

    wiring_config = containers.WiringConfiguration(
        packages=["lintel.api.routes"],
        modules=["lintel.api.deps"],
    )

    # ---------------------------------------------------------------------------
    # Sentinel — replaced by lifespan via container.X.override(providers.Object(inst))
    # ---------------------------------------------------------------------------

    # Event infrastructure
    event_store: providers.Provider[Any] = providers.Object(None)
    event_bus: providers.Provider[Any] = providers.Object(None)

    # Entity stores
    repository_store: providers.Provider[Any] = providers.Object(None)
    skill_store: providers.Provider[Any] = providers.Object(None)
    credential_store: providers.Provider[Any] = providers.Object(None)
    ai_provider_store: providers.Provider[Any] = providers.Object(None)
    project_store: providers.Provider[Any] = providers.Object(None)
    work_item_store: providers.Provider[Any] = providers.Object(None)
    pipeline_store: providers.Provider[Any] = providers.Object(None)
    environment_store: providers.Provider[Any] = providers.Object(None)
    trigger_store: providers.Provider[Any] = providers.Object(None)
    variable_store: providers.Provider[Any] = providers.Object(None)
    user_store: providers.Provider[Any] = providers.Object(None)
    team_store: providers.Provider[Any] = providers.Object(None)
    policy_store: providers.Provider[Any] = providers.Object(None)
    notification_rule_store: providers.Provider[Any] = providers.Object(None)
    audit_entry_store: providers.Provider[Any] = providers.Object(None)
    code_artifact_store: providers.Provider[Any] = providers.Object(None)
    test_result_store: providers.Provider[Any] = providers.Object(None)
    approval_request_store: providers.Provider[Any] = providers.Object(None)
    chat_store: providers.Provider[Any] = providers.Object(None)
    agent_definition_store: providers.Provider[Any] = providers.Object(None)
    model_store: providers.Provider[Any] = providers.Object(None)
    model_assignment_store: providers.Provider[Any] = providers.Object(None)
    mcp_server_store: providers.Provider[Any] = providers.Object(None)
    sandbox_store: providers.Provider[Any] = providers.Object(None)
    tag_store: providers.Provider[Any] = providers.Object(None)
    board_store: providers.Provider[Any] = providers.Object(None)
    automation_store: providers.Provider[Any] = providers.Object(None)

    # Compliance & Governance stores
    regulation_store: providers.Provider[Any] = providers.Object(None)
    compliance_policy_store: providers.Provider[Any] = providers.Object(None)
    procedure_store: providers.Provider[Any] = providers.Object(None)
    practice_store: providers.Provider[Any] = providers.Object(None)
    strategy_store: providers.Provider[Any] = providers.Object(None)
    kpi_store: providers.Provider[Any] = providers.Object(None)
    experiment_store: providers.Provider[Any] = providers.Object(None)
    compliance_metric_store: providers.Provider[Any] = providers.Object(None)
    knowledge_entry_store: providers.Provider[Any] = providers.Object(None)
    knowledge_extraction_store: providers.Provider[Any] = providers.Object(None)
    architecture_decision_store: providers.Provider[Any] = providers.Object(None)

    # Repository provider (GitHub API access for commits, PRs, etc.)
    repo_provider: providers.Provider[Any] = providers.Object(None)

    # Domain services
    model_router: providers.Provider[Any] = providers.Object(None)
    chat_router: providers.Provider[Any] = providers.Object(None)
    agent_runtime: providers.Provider[Any] = providers.Object(None)
    command_dispatcher: providers.Provider[Any] = providers.Object(None)
    workflow_executor: providers.Provider[Any] = providers.Object(None)
    sandbox_manager: providers.Provider[Any] = providers.Object(None)
    mcp_tool_client: providers.Provider[Any] = providers.Object(None)

    # Projections
    projection_engine: providers.Provider[Any] = providers.Object(None)
    thread_status_projection: providers.Provider[Any] = providers.Object(None)
    quality_metrics_projection: providers.Provider[Any] = providers.Object(None)
    task_backlog_projection: providers.Provider[Any] = providers.Object(None)


def wire_container(
    container: AppContainer, stores: dict[str, Any], services: dict[str, Any]
) -> None:
    """Populate container providers from pre-constructed store/service instances.

    Called from lifespan after all stores and services are constructed so the
    container reflects the live objects that routes depend on.
    """
    for name, instance in {**stores, **services}.items():
        provider: providers.Provider[Any] | None = getattr(container, name, None)
        if provider is not None:
            provider.override(providers.Object(instance))
