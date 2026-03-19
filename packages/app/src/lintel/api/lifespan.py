"""FastAPI lifespan context manager — wires stores, services, and projections."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import asyncpg
    from fastapi import FastAPI
    from langgraph.graph.state import CompiledStateGraph

from lintel.api.store_wiring import create_in_memory_stores, create_postgres_stores, wire_stores
from lintel.event_bus.in_memory import InMemoryEventBus
from lintel.projections.audit import AuditProjection
from lintel.projections.engine import InMemoryProjectionEngine
from lintel.projections.quality_metrics import QualityMetricsProjection
from lintel.projections.task_backlog import TaskBacklogProjection
from lintel.projections.thread_status import ThreadStatusProjection
from lintel.repos.github_provider import GitHubRepoProvider
from lintel.sandbox.docker_backend import DockerSandboxManager


async def _seed_defaults(stores: dict[str, Any]) -> None:
    """Seed built-in agent definitions and skills into stores."""
    import dataclasses

    from lintel.domain.seed import DEFAULT_AGENTS, DEFAULT_SKILLS

    agent_store = stores["agent_definition_store"]
    for agent in DEFAULT_AGENTS:
        data = dataclasses.asdict(agent)
        for key, value in data.items():
            if isinstance(value, frozenset | tuple):
                data[key] = list(value)
        existing = await agent_store.get(agent.agent_id)
        if existing is None:
            await agent_store.create(data)

    skill_store = stores["skill_store"]
    for skill in DEFAULT_SKILLS:
        await skill_store.register(
            skill_id=skill.skill_id,
            version=skill.version,
            name=skill.name,
            input_schema=skill.input_schema or {},
            output_schema=skill.output_schema or {},
            execution_mode=skill.execution_mode.value,
            description=skill.description,
            allowed_agent_roles=skill.allowed_agent_roles,
        )
        if hasattr(skill_store, "_metadata"):
            skill_store._metadata[skill.skill_id] = {
                "description": skill.description,
                "content": skill.system_prompt,
                "category": skill.category.value,
                "tags": list(skill.tags),
                "allowed_agent_roles": list(skill.allowed_agent_roles),
                "is_builtin": skill.is_builtin,
                "enabled": skill.enabled,
            }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan: creates stores, wires services, starts background tasks."""
    from lintel.observability.logging import configure_logging

    log_level = os.environ.get("LINTEL_LOG_LEVEL", "INFO").upper()
    configure_logging(log_level=log_level, log_format="console")

    from lintel.observability.metrics import configure_metrics
    from lintel.observability.tracing import configure_tracing

    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    configure_tracing(otel_endpoint=otel_endpoint)
    configure_metrics()

    storage_backend = os.environ.get("LINTEL_STORAGE_BACKEND", "").lower()
    dsn = os.environ.get("LINTEL_DB_DSN")
    db_pool = None

    if not storage_backend:
        storage_backend = "postgres" if dsn else "memory"

    if storage_backend == "postgres":
        if not dsn:
            msg = "LINTEL_STORAGE_BACKEND=postgres requires LINTEL_DB_DSN to be set"
            raise RuntimeError(msg)
        import asyncpg

        db_pool = await asyncpg.create_pool(dsn)  # type: ignore[no-untyped-call]
        stores = create_postgres_stores(cast("asyncpg.Pool", db_pool))
    else:
        stores = create_in_memory_stores()

    for name, store in stores.items():
        setattr(app.state, name, store)

    from lintel.api.domain.command_dispatcher import InMemoryCommandDispatcher
    from lintel.chat_api.chat_router import ChatRouter
    from lintel.models.router import DefaultModelRouter
    from lintel.workflows.workflow_executor import WorkflowExecutor

    dispatcher = InMemoryCommandDispatcher()
    event_store = stores["event_store"]

    ollama_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    model_router = DefaultModelRouter(
        ollama_api_base=ollama_base,
        model_store=stores["model_store"],
        ai_provider_store=stores["ai_provider_store"],
        model_assignment_store=stores["model_assignment_store"],
    )

    from lintel.agents.runtime import AgentRuntime
    from lintel.infrastructure.mcp.tool_client import MCPToolClient

    mcp_tool_client = MCPToolClient()
    agent_runtime = AgentRuntime(
        event_store=event_store,
        model_router=model_router,
        mcp_tool_client=mcp_tool_client,
        mcp_server_store=stores["mcp_server_store"],
    )
    app.state.agent_runtime = agent_runtime
    app.state.model_router = model_router

    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()

    def _graph_factory(workflow_type: str) -> CompiledStateGraph:  # type: ignore[type-arg]
        from lintel.workflows.registry import get_workflow_builder

        builder_fn = get_workflow_builder(workflow_type)
        state_graph = builder_fn()
        approval_nodes = [name for name in state_graph.nodes if "approval_gate" in name]
        return state_graph.compile(
            checkpointer=_checkpointer,
            interrupt_before=approval_nodes or None,
        )

    from lintel.observability.step_metrics import OtelStepMetricsRecorder

    executor = WorkflowExecutor(
        event_store=event_store,
        graph_factory=_graph_factory,
        agent_runtime=agent_runtime,
        app_state=app.state,
        step_metrics=OtelStepMetricsRecorder(),
    )
    app.state.workflow_executor = executor

    from lintel.workflows.commands import StartWorkflow

    dispatcher.register(StartWorkflow, executor.execute)
    app.state.command_dispatcher = dispatcher

    # --- Channel registry setup ---
    from lintel.channels.registry import ChannelRegistry

    channel_registry = ChannelRegistry()
    app.state.channel_registry = channel_registry

    # Register Slack adapter if configured (placeholder - real Slack adapter
    # is initialized elsewhere via Bolt)

    # Register Telegram adapter: try env vars first, then fall back to credential store
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if telegram_token:
        from lintel.telegram.adapter import TelegramChannelAdapter

        telegram_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        telegram_adapter = TelegramChannelAdapter(
            bot_token=telegram_token,
            webhook_secret=telegram_secret,
        )
        from lintel.contracts.channel_type import ChannelType

        channel_registry.register(ChannelType.TELEGRAM, telegram_adapter)
        app.state.telegram_adapter = telegram_adapter
    else:
        # Restore from credential store (token saved via Settings > Channels UI)
        from lintel.settings_api.channels_router import restore_telegram_from_store

        await restore_telegram_from_store(app)

    chat_router = ChatRouter(
        model_router=model_router,
        mcp_tool_client=mcp_tool_client,
        mcp_server_store=stores["mcp_server_store"],
    )
    app.state.chat_router = chat_router
    app.state.mcp_tool_client = mcp_tool_client

    await _seed_defaults(stores)

    event_bus = InMemoryEventBus()
    app.state.event_bus = event_bus
    event_store.set_event_bus(event_bus)

    thread_status = ThreadStatusProjection()
    task_backlog = TaskBacklogProjection()
    audit_projection = AuditProjection(stores["audit_entry_store"])
    quality_metrics = QualityMetricsProjection()
    engine = InMemoryProjectionEngine(event_bus=event_bus)
    await engine.register(thread_status)
    await engine.register(task_backlog)
    await engine.register(audit_projection)
    await engine.register(quality_metrics)
    await engine.start()

    app.state.thread_status_projection = thread_status
    app.state.task_backlog_projection = task_backlog
    app.state.quality_metrics_projection = quality_metrics
    app.state.projection_engine = engine

    sandbox_manager = DockerSandboxManager()
    app.state.sandbox_manager = sandbox_manager

    # Optionally enable OpenShell backend alongside Docker
    sandbox_backend_env = os.environ.get("SANDBOX_BACKEND", "docker")
    if sandbox_backend_env in ("openshell", "both"):
        from lintel.sandbox.openshell_backend import OpenShellSandboxManager

        openshell_manager = OpenShellSandboxManager()
        app.state.openshell_manager = openshell_manager

    async def _recover_sandboxes(
        recover_fn: Any,  # noqa: ANN401
        store: Any,  # noqa: ANN401
        label: str,
    ) -> None:
        import logging

        try:
            recovered = await recover_fn()
            if recovered:
                logger = logging.getLogger("lintel")
                logger.info("Recovered %d %s sandboxes", len(recovered), label)
                for meta in recovered:
                    try:
                        await store.add(meta["sandbox_id"], meta)
                    except Exception:
                        logger.warning(
                            "Failed to restore %s metadata for %s", label, meta["sandbox_id"]
                        )
        except Exception:
            pass

    await _recover_sandboxes(sandbox_manager.recover_containers, app.state.sandbox_store, "Docker")
    if hasattr(app.state, "openshell_manager"):
        await _recover_sandboxes(
            app.state.openshell_manager.recover_sandboxes, app.state.sandbox_store, "OpenShell"
        )

    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo_provider = GitHubRepoProvider(token=github_token) if github_token else None

    from lintel.api.container import AppContainer, wire_container

    container = AppContainer()
    services = {
        "event_bus": event_bus,
        "model_router": model_router,
        "chat_router": chat_router,
        "agent_runtime": agent_runtime,
        "command_dispatcher": dispatcher,
        "workflow_executor": executor,
        "sandbox_manager": sandbox_manager,
        "mcp_tool_client": mcp_tool_client,
        "repo_provider": repo_provider,
        "projection_engine": engine,
        "thread_status_projection": thread_status,
        "quality_metrics_projection": quality_metrics,
        "task_backlog_projection": task_backlog,
    }
    wire_container(container, stores, services)
    container.wire(
        packages=["lintel.api.routes"],
        modules=["lintel.api.deps"],
    )

    wire_stores(stores, repo_provider)

    app.state.code_artifact_store = stores["code_artifact_store"]
    app.state.test_result_store = stores["test_result_store"]
    app.state.pipeline_store = stores["pipeline_store"]
    app.state.credential_store = stores["credential_store"]
    app.state.integration_pattern_store = stores["integration_patterns"]
    app.state.process_mining_store = stores["process_mining"]
    app.state.container = container

    import asyncio

    from lintel.automations_api.scheduler import AutomationScheduler

    async def _fire_automation(
        auto: Any,  # noqa: ANN401
        metadata: dict[str, Any],
    ) -> str:
        from uuid import uuid4

        from lintel.domain.events import AutomationFired
        from lintel.workflows.types import PipelineRun

        run_id = str(uuid4())
        pipeline_run = PipelineRun(
            run_id=run_id,
            project_id=auto.project_id,
            work_item_id="",
            workflow_definition_id=auto.trigger_config.get("workflow_definition_id", ""),
            trigger_type=f"automation:{auto.automation_id}",
        )
        await stores["pipeline_store"].add(pipeline_run)
        event = AutomationFired(
            payload={
                "resource_id": auto.automation_id,
                "pipeline_run_id": run_id,
                "trigger_type": metadata.get("trigger", "unknown"),
            },
        )
        await event_bus.publish(event)
        return run_id

    automation_scheduler = AutomationScheduler(
        automation_store=stores["automation_store"],
        fire_fn=_fire_automation,
    )

    all_automations = await stores["automation_store"].list_all()

    async def _on_event(event: Any) -> None:  # noqa: ANN401
        await automation_scheduler.handle_event(event)

    event_types: set[str] = set()
    for auto in all_automations:
        if auto.trigger_type == "event" and auto.enabled:
            for et in auto.trigger_config.get("event_types", []):
                event_types.add(et)
    if event_types:
        await event_bus.subscribe(
            frozenset(event_types),
            type("_AutoEventHandler", (), {"handle": staticmethod(_on_event)})(),
        )

    async def _on_pipeline_complete(event: Any) -> None:  # noqa: ANN401
        payload = event.payload or {}
        run_id = payload.get("resource_id", "")
        trigger = payload.get("trigger_type", "")
        if trigger.startswith("automation:"):
            aid = trigger.split(":", 1)[1]
            await automation_scheduler.mark_run_completed(aid, run_id)

    await event_bus.subscribe(
        frozenset({"PipelineRunCompleted", "PipelineRunFailed"}),
        type("_PipelineCompleteHandler", (), {"handle": staticmethod(_on_pipeline_complete)})(),
    )

    background_tasks: set[asyncio.Task[Any]] = set()
    app.state._background_tasks = background_tasks
    scheduler_task = asyncio.create_task(automation_scheduler.run())
    app.state._background_tasks.add(scheduler_task)
    scheduler_task.add_done_callback(app.state._background_tasks.discard)

    # Start Telegram polling if adapter is configured
    tg_adapter: object | None = getattr(app.state, "telegram_adapter", None)
    if tg_adapter is not None:
        from lintel.settings_api.channels_router import start_telegram_polling

        await start_telegram_polling(app, tg_adapter)

    yield

    container.unwire()
    scheduler_task.cancel()
    from lintel.settings_api.channels_router import stop_telegram_polling

    await stop_telegram_polling(app)
    await engine.stop()
    if db_pool is not None:
        await db_pool.close()
