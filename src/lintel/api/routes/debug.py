"""Debug endpoint — run a single workflow node in isolation."""

from __future__ import annotations

import asyncio
import importlib
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter()
logger = structlog.get_logger()

# Background tasks — prevent garbage collection of fire-and-forget tasks
_background_tasks: set[asyncio.Task[None]] = set()

# Map node_name → (module_path, function_name)
NODE_REGISTRY: dict[str, tuple[str, str]] = {
    "ingest": ("lintel.workflows.nodes.ingest", "ingest_message"),
    "route": ("lintel.workflows.nodes.route", "route_intent"),
    "setup_workspace": ("lintel.workflows.nodes.setup_workspace", "setup_workspace"),
    "research": ("lintel.workflows.nodes.research", "research_codebase"),
    "plan": ("lintel.workflows.nodes.plan", "plan_work"),
    "implement": ("lintel.workflows.nodes.implement", "spawn_implementation"),
    "review": ("lintel.workflows.nodes.review", "review_output"),
    "close": ("lintel.workflows.nodes.close", "close_workflow"),
    "triage": ("lintel.workflows.nodes.triage", "triage_issue"),
    "analyse": ("lintel.workflows.nodes.analyse", "analyse_code"),
}


class DebugRunNodeRequest(BaseModel):
    """Request body for POST /debug/run-node."""

    node_name: str = Field(description="Node to run: plan, implement, research, review, etc.")
    sandbox_id: str | None = Field(default=None, description="Existing sandbox ID (or auto-pick)")
    prompt: str = Field(default="", description="User request / prompt text")
    intent: str = Field(default="feature", description="Workflow intent")
    research_context: str = Field(default="", description="Research context for plan node")
    plan: dict[str, Any] | None = Field(default=None, description="Plan dict for implement node")
    workspace_path: str = Field(default="", description="Workspace path inside sandbox")
    feature_branch: str = Field(default="", description="Feature branch name")
    project_id: str = Field(default="", description="Project ID")
    repo_url: str = Field(default="", description="Repository URL")
    credential_ids: list[str] = Field(
        default_factory=list, description="Credential IDs for repo auth"
    )
    timeout_seconds: int = Field(default=300, description="Max seconds to wait for node")


class DebugRunNodeResponse(BaseModel):
    """Response from debug node execution (returned immediately)."""

    run_id: str
    node_name: str
    sandbox_id: str | None
    stage_id: str
    status: str


@router.post("/debug/run-node")
async def run_node(body: DebugRunNodeRequest, request: Request) -> DebugRunNodeResponse:
    """Run a single workflow node in isolation for debugging.

    Returns immediately with run_id and stage_id. The node runs in the
    background. Use the existing pipeline SSE endpoints to stream progress:
      - GET /pipelines/{run_id}/stages/{stage_id}/logs  (stage logs)
      - GET /pipelines/{run_id}/events                  (status changes)
      - GET /pipelines/{run_id}                         (final result)
    """
    if body.node_name not in NODE_REGISTRY:
        return DebugRunNodeResponse(
            run_id="",
            node_name=body.node_name,
            sandbox_id=None,
            stage_id="",
            status="failed",
        )

    run_id = uuid4().hex
    stage_id = uuid4().hex
    app_state = request.app.state
    sandbox_id = body.sandbox_id

    # Auto-pick a sandbox if not provided and node needs one
    nodes_needing_sandbox = {"research", "plan", "implement", "review", "setup_workspace"}
    if sandbox_id is None and body.node_name in nodes_needing_sandbox:
        sandbox_store = getattr(app_state, "sandbox_store", None)
        if sandbox_store is not None:
            all_sandboxes = await sandbox_store.list_all()
            for sb in all_sandboxes:
                sb_id = (
                    sb.get("sandbox_id")
                    if isinstance(sb, dict)
                    else getattr(sb, "sandbox_id", None)
                )
                if sb_id:
                    sandbox_id = sb_id
                    break

    # Create a lightweight pipeline run for stage tracking
    pipeline_store = getattr(app_state, "pipeline_store", None)

    if pipeline_store is not None:
        from lintel.contracts.types import PipelineRun, PipelineStatus, Stage, StageStatus

        stage = Stage(
            stage_id=stage_id,
            name=body.node_name,
            stage_type=body.node_name,
            status=StageStatus.PENDING,
            inputs=None,
            outputs=None,
            error="",
            duration_ms=0,
            started_at="",
            finished_at="",
            logs=(),
            retry_count=0,
            attempts=(),
        )
        pipeline_run = PipelineRun(
            run_id=run_id,
            project_id=body.project_id or "debug",
            work_item_id="debug",
            workflow_definition_id="debug",
            status=PipelineStatus.RUNNING,
            stages=(stage,),
            trigger_type=f"debug:{body.node_name}",
            trigger_id=uuid4().hex,
            environment_id="",
            created_at=datetime.now(tz=UTC).isoformat(),
        )
        await pipeline_store.add(pipeline_run)

    # Build the workflow state
    state: dict[str, Any] = {
        "thread_ref": f"debug/debug/{run_id}",
        "correlation_id": uuid4().hex,
        "current_phase": "debug",
        "sanitized_messages": [body.prompt] if body.prompt else [],
        "intent": body.intent,
        "plan": body.plan or {},
        "agent_outputs": [],
        "pending_approvals": [],
        "sandbox_id": sandbox_id,
        "sandbox_results": [],
        "pr_url": "",
        "error": None,
        "run_id": run_id,
        "project_id": body.project_id or "debug",
        "work_item_id": "debug",
        "repo_url": body.repo_url,
        "repo_urls": (body.repo_url,) if body.repo_url else (),
        "repo_branch": "main",
        "feature_branch": body.feature_branch,
        "credential_ids": tuple(body.credential_ids),
        "environment_id": "",
        "workspace_path": body.workspace_path or "/workspace/repo",
        "research_context": body.research_context,
        "token_usage": [],
        "review_cycles": 0,
    }

    # Build config matching WorkflowExecutor._build_config()
    agent_runtime = getattr(app_state, "agent_runtime", None)
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "agent_runtime": agent_runtime,
            "app_state": app_state,
            "pipeline_store": pipeline_store,
            "sandbox_manager": getattr(app_state, "sandbox_manager", None),
            "credential_store": getattr(app_state, "credential_store", None),
            "code_artifact_store": getattr(app_state, "code_artifact_store", None),
            "test_result_store": getattr(app_state, "test_result_store", None),
        }
    }

    # Register runtime for nodes that use _runtime_registry fallback
    if agent_runtime is not None:
        from lintel.workflows.nodes._runtime_registry import register as _register_runtime

        _register_runtime(
            run_id,
            agent_runtime,
            getattr(app_state, "sandbox_manager", None),
            app_state,
        )

    logger.info(
        "debug_run_node_dispatched",
        node_name=body.node_name,
        run_id=run_id,
        stage_id=stage_id,
        sandbox_id=sandbox_id,
        prompt_preview=body.prompt[:200],
        repo_url=body.repo_url,
        credential_ids=body.credential_ids,
        has_agent_runtime=agent_runtime is not None,
        has_pipeline_store=pipeline_store is not None,
        has_sandbox_manager=getattr(app_state, "sandbox_manager", None) is not None,
    )

    # Launch the node in the background
    task = asyncio.create_task(
        _run_node_background(
            body.node_name, run_id, stage_id, state, config,
            pipeline_store, body.timeout_seconds,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return DebugRunNodeResponse(
        run_id=run_id,
        node_name=body.node_name,
        sandbox_id=sandbox_id,
        stage_id=stage_id,
        status="running",
    )


async def _run_node_background(
    node_name: str,
    run_id: str,
    stage_id: str,
    state: dict[str, Any],
    config: dict[str, Any],
    pipeline_store: Any,  # noqa: ANN401
    timeout_seconds: int,
) -> None:
    """Execute the node function in the background, updating pipeline store."""
    # If a repo_url is set and this node needs a cloned repo, run setup_workspace first
    nodes_needing_repo = {"research", "plan", "implement", "review", "analyse"}
    repo_url = state.get("repo_url", "")
    if node_name in nodes_needing_repo and repo_url:
        logger.info(
            "debug_auto_setup_workspace",
            node_name=node_name,
            run_id=run_id,
            repo_url=repo_url,
        )
        try:
            setup_mod = importlib.import_module("lintel.workflows.nodes.setup_workspace")
            setup_result = await asyncio.wait_for(
                setup_mod.setup_workspace(state, config),
                timeout=timeout_seconds,
            )
            # Propagate sandbox_id, workspace_path, feature_branch from setup
            if isinstance(setup_result, dict):
                for key in ("sandbox_id", "workspace_path", "feature_branch"):
                    if key in setup_result:
                        state[key] = setup_result[key]
            # Ensure new sandbox has Claude Code credentials
            new_sandbox_id = state.get("sandbox_id")
            sandbox_mgr = config.get("configurable", {}).get("sandbox_manager")
            if new_sandbox_id and sandbox_mgr:
                from lintel.infrastructure.models.claude_code import (
                    refresh_credentials_for_sandbox,
                )

                await refresh_credentials_for_sandbox(sandbox_mgr, new_sandbox_id)
            logger.info(
                "debug_auto_setup_workspace_done",
                run_id=run_id,
                sandbox_id=state.get("sandbox_id"),
                workspace_path=state.get("workspace_path"),
            )
        except Exception as exc:
            logger.exception(
                "debug_auto_setup_workspace_failed", run_id=run_id, error=str(exc)
            )
            # Continue anyway — the node will fail with a clear error

    module_path, func_name = NODE_REGISTRY[node_name]
    module = importlib.import_module(module_path)
    node_func = getattr(module, func_name)

    start = time.monotonic()
    status = "completed"
    output: dict[str, Any] = {}
    error = ""

    try:
        result = await asyncio.wait_for(
            node_func(state, config),
            timeout=timeout_seconds,
        )
        output = result if isinstance(result, dict) else {"result": str(result)}
    except TimeoutError:
        status = "failed"
        error = f"Node timed out after {timeout_seconds}s"
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("debug_run_node_error", node_name=node_name, run_id=run_id)

    duration_ms = int((time.monotonic() - start) * 1000)

    # Update pipeline run with final status and output
    if pipeline_store is not None:
        from lintel.contracts.types import PipelineStatus, StageStatus

        run = await pipeline_store.get(run_id)
        if run is not None:
            from dataclasses import replace

            final_stage_status = (
                StageStatus.SUCCEEDED if status == "completed" else StageStatus.FAILED
            )
            updated_stages = []
            for s in run.stages:
                if s.stage_id == stage_id:
                    s = replace(
                        s,
                        status=final_stage_status,
                        outputs=output,
                        error=error,
                        duration_ms=duration_ms,
                        finished_at=datetime.now(tz=UTC).isoformat(),
                    )
                updated_stages.append(s)
            final_status = (
                PipelineStatus.SUCCEEDED
                if status == "completed"
                else PipelineStatus.FAILED
            )
            updated_run = replace(
                run,
                stages=tuple(updated_stages),
                status=final_status,
            )
            await pipeline_store.update(updated_run)

    logger.info(
        "debug_run_node_complete",
        node_name=node_name,
        run_id=run_id,
        status=status,
        duration_ms=duration_ms,
        error=error[:200] if error else "",
    )


@router.get("/debug/nodes")
async def list_nodes() -> dict[str, Any]:
    """List available nodes for debugging."""
    return {
        "nodes": sorted(NODE_REGISTRY.keys()),
        "descriptions": {
            "ingest": "Parse and sanitize incoming message",
            "route": "Classify intent (feature, bug, refactor, etc.)",
            "setup_workspace": "Create sandbox, clone repo, create branch",
            "research": "Research codebase context from sandbox",
            "plan": "Generate implementation plan from research + request",
            "implement": "Write code based on plan",
            "review": "Review implementation output",
            "close": "Create PR and finalize",
            "triage": "Classify issue priority/type",
            "analyse": "Analyse code for quality/issues",
        },
    }
