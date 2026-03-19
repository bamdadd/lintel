"""Stage-level route handlers."""

import asyncio
from dataclasses import asdict, replace
from datetime import UTC, datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.contracts.types import ThreadRef
from lintel.pipelines_api._helpers import _find_stage
from lintel.pipelines_api._store import InMemoryPipelineStore, pipeline_store_provider
from lintel.workflows.commands import StartWorkflow
from lintel.workflows.events import (
    PipelineStageApproved,
    PipelineStageRejected,
    PipelineStageRetried,
    StageReportEdited,
    StageReportRegenerated,
)
from lintel.workflows.types import PipelineRun, PipelineStatus, StageStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class ReportVersionService:
    """Manages stage report version history stored in app state."""

    @staticmethod
    def report_key(stage_name: str) -> str:
        """Map stage name to the output key holding the report."""
        if stage_name in ("research", "approve_research"):
            return "research_report"
        if stage_name in ("plan", "approve_spec"):
            return "plan"
        return "report"

    @staticmethod
    def get_versions(request: Request, run_id: str, stage_id: str) -> list[dict[str, object]]:
        """Retrieve report version history from app state."""
        versions_store: dict[str, list[dict[str, object]]] = getattr(
            request.app.state, "_report_versions", {}
        )
        key = f"{run_id}:{stage_id}"
        return versions_store.get(key, [])

    @staticmethod
    def add_version(
        request: Request,
        run_id: str,
        stage_id: str,
        content: str,
        editor: str,
        version_type: str = "edit",
    ) -> dict[str, object]:
        """Append a new version to the report history."""
        if not hasattr(request.app.state, "_report_versions"):
            request.app.state._report_versions = {}
        versions_store: dict[str, list[dict[str, object]]] = request.app.state._report_versions
        key = f"{run_id}:{stage_id}"
        versions = versions_store.setdefault(key, [])
        from lintel.persistence.data_models import ReportVersion

        ver = ReportVersion(
            version=len(versions) + 1,
            content=content,
            editor=editor,
            type=version_type,
            timestamp=datetime.now(UTC).isoformat(),
        )
        data = ver.model_dump()
        versions.append(data)
        return data


class ReportEditPayload(BaseModel):
    """Body for editing a stage report."""

    content: str = Field(..., description="Updated report content (Markdown)")
    editor: str = Field(default="user", description="Who made the edit")


class RegeneratePayload(BaseModel):
    """Body for regenerating a stage report."""

    guidance: str = Field(default="", description="Optional prompt to guide regeneration")


@router.get("/pipelines/{run_id}/stages")
async def list_stages(
    run_id: str,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return [asdict(s) for s in run.stages]


@router.get("/pipelines/{run_id}/stages/{stage_id}")
async def get_stage(
    run_id: str,
    stage_id: str,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    for stage in run.stages:
        if stage.stage_id == stage_id:
            return asdict(stage)
    raise HTTPException(status_code=404, detail="Stage not found")


async def _redispatch_pipeline(request: Request, run: PipelineRun) -> None:
    """Re-dispatch a pipeline via StartWorkflow when the graph session is lost."""
    dispatcher = getattr(request.app.state, "command_dispatcher", None)
    if dispatcher is None:
        logger.warning("redispatch_no_dispatcher", extra={"run_id": run.run_id})
        return

    # Resolve repo info from project
    repo_url = ""
    repo_urls: tuple[str, ...] = ()
    repo_branch = "main"
    credential_ids: tuple[str, ...] = ()
    project_store = getattr(request.app.state, "project_store", None)
    repo_store = getattr(request.app.state, "repo_store", None)
    if project_store and run.project_id:
        try:
            project = await project_store.get(run.project_id)
            if project:
                repo_branch = project.get("default_branch", "main")
                credential_ids = tuple(project.get("credential_ids", ()))
                repo_ids = project.get("repo_ids", ())
                if isinstance(repo_ids, list | tuple) and repo_ids and repo_store:
                    first_repo = await repo_store.get(repo_ids[0])
                    if first_repo is not None:
                        repo_url = (
                            first_repo.url
                            if hasattr(first_repo, "url")
                            else first_repo.get("url", "")
                        )
                        all_urls: list[str] = [repo_url] if repo_url else []
                        for rid in repo_ids[1:]:
                            extra = await repo_store.get(rid)
                            if extra is not None:
                                u = extra.url if hasattr(extra, "url") else extra.get("url", "")
                                if u:
                                    all_urls.append(u)
                        repo_urls = tuple(all_urls)
        except Exception:
            logger.warning("redispatch_project_lookup_failed", exc_info=True)

    # Resolve work item description for sanitized_messages
    description = ""
    work_item_store = getattr(request.app.state, "work_item_store", None)
    if work_item_store and run.work_item_id:
        try:
            item = await work_item_store.get(run.work_item_id)
            if item:
                description = item.get("description", item.get("title", ""))
        except Exception:
            pass

    thread_ref = ThreadRef(
        workspace_id="lintel",
        channel_id=f"pipeline:{run.project_id}",
        thread_ts=run.run_id,
    )
    command = StartWorkflow(
        thread_ref=thread_ref,
        workflow_type=run.workflow_definition_id or "feature_to_pr",
        sanitized_messages=(description,) if description else (),
        project_id=run.project_id,
        work_item_id=run.work_item_id,
        run_id=run.run_id,
        repo_url=repo_url,
        repo_urls=repo_urls,
        repo_branch=repo_branch,
        credential_ids=credential_ids,
        continue_from_run_id=run.run_id,
    )
    task = asyncio.create_task(dispatcher.dispatch(command))
    bg: set[asyncio.Task[None]] = getattr(request.app.state, "_background_tasks", set())
    request.app.state._background_tasks = bg
    bg.add(task)
    task.add_done_callback(bg.discard)
    logger.info("pipeline_redispatched", extra={"run_id": run.run_id})


@router.post("/pipelines/{run_id}/stages/{stage_id}/retry")
async def retry_stage(
    run_id: str,
    stage_id: str,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Retry a failed or stuck stage. Resets it to running and re-invokes the node."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("running", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry stage in '{status}' state (must be running or failed)",
        )

    if stage.retry_count >= 3:
        raise HTTPException(
            status_code=409,
            detail="Maximum retry count (3) reached for this stage",
        )

    # Reset stage to running
    now = datetime.now(UTC).isoformat()
    new_stages = []
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(
                replace(
                    s,
                    status=StageStatus.RUNNING,
                    started_at=now,
                    finished_at="",
                    error="",
                    duration_ms=0,
                    logs=(),
                    retry_count=s.retry_count + 1,
                )
            )
        else:
            new_stages.append(s)

    updated = replace(run, stages=tuple(new_stages))
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageRetried(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "retry_count": stage.retry_count + 1,
            }
        ),
        stream_id=f"run:{run_id}",
    )

    # Re-invoke the workflow executor if the session is still alive
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None and run_id in getattr(executor, "_suspended_runs", {}):
        task = asyncio.create_task(executor.resume(run_id))
        bg: set[asyncio.Task[None]] = getattr(request.app.state, "_background_tasks", set())
        request.app.state._background_tasks = bg
        bg.add(task)
        task.add_done_callback(bg.discard)
    else:
        # Session lost (server restart or failed pipeline) — re-dispatch workflow
        await _redispatch_pipeline(request, updated)

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


@router.post("/pipelines/{run_id}/stages/{stage_id}/reject")
async def reject_stage(
    run_id: str,
    stage_id: str,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Reject a stage that is waiting for human approval, failing the pipeline."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status != "waiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject stage in '{status}' state (must be waiting_approval)",
        )

    # Mark stage as rejected, remaining pending stages as skipped
    new_stages = []
    rejected = False
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(replace(s, status=StageStatus.REJECTED))
            rejected = True
        elif rejected:
            s_status = s.status.value if hasattr(s.status, "value") else str(s.status)
            if s_status == "pending":
                new_stages.append(replace(s, status=StageStatus.SKIPPED))
            else:
                new_stages.append(s)
        else:
            new_stages.append(s)

    updated = replace(
        run,
        stages=tuple(new_stages),
        status=PipelineStatus.FAILED,
    )
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageRejected(
            payload={"resource_id": stage_id, "run_id": run_id, "stage_name": stage.name}
        ),
        stream_id=f"run:{run_id}",
    )

    # Clean up suspended run in executor
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        executor._suspended_runs.pop(run_id, None)

    # Fail the work item
    if executor is not None and hasattr(executor, "_app_state") and executor._app_state:
        work_item_store = getattr(executor._app_state, "work_item_store", None)
        pipeline_store = getattr(executor._app_state, "pipeline_store", None)
        if work_item_store and pipeline_store:
            try:
                full_run = await pipeline_store.get(run_id)
                if full_run and hasattr(full_run, "trigger_type"):
                    trigger = full_run.trigger_type
                    if trigger.startswith("chat:"):
                        conversation_id = trigger[5:]
                        chat_store = getattr(executor._app_state, "chat_store", None)
                        if chat_store:
                            await chat_store.add_message(
                                conversation_id,
                                user_id="system",
                                display_name="Lintel",
                                role="agent",
                                content=(
                                    f"🚫 **{stage.name}** — rejected\n"
                                    f"Pipeline has been stopped.\n"
                                    f"[View pipeline →](/pipelines/{run_id})"
                                ),
                            )
            except Exception:
                pass

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


@router.post("/pipelines/{run_id}/stages/{stage_id}/approve")
async def approve_stage(
    run_id: str,
    stage_id: str,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Approve a stage that is waiting for human approval and resume the workflow."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status != "waiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve stage in '{status}' state (must be waiting_approval)",
        )

    # Mark stage as approved
    new_stages = []
    for s in run.stages:
        sid = s.stage_id
        if sid == stage_id:
            new_stages.append(replace(s, status=StageStatus.APPROVED))
        else:
            new_stages.append(s)

    updated = replace(
        run,
        stages=tuple(new_stages),
        status=PipelineStatus.RUNNING,
    )
    await store.update(updated)
    await dispatch_event(
        request,
        PipelineStageApproved(
            payload={"resource_id": stage_id, "run_id": run_id, "stage_name": stage.name}
        ),
        stream_id=f"run:{run_id}",
    )

    # Resume the workflow in the background
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        task = asyncio.create_task(executor.resume(run_id))
        request.app.state._background_tasks = getattr(
            request.app.state,
            "_background_tasks",
            set(),
        )
        request.app.state._background_tasks.add(task)
        task.add_done_callback(request.app.state._background_tasks.discard)

    return asdict(_find_stage(updated, stage_id))  # type: ignore[arg-type]


@router.patch("/pipelines/{run_id}/stages/{stage_id}/report")
async def edit_stage_report(
    run_id: str,
    stage_id: str,
    body: ReportEditPayload,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Edit the report output of a completed or waiting_approval stage."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("succeeded", "waiting_approval"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit report in '{status}' state",
        )

    # Update the report in stage outputs
    rkey = ReportVersionService.report_key(stage.name)
    outputs = dict(stage.outputs) if stage.outputs else {}
    outputs[rkey] = body.content

    new_stages = [replace(s, outputs=outputs) if s.stage_id == stage_id else s for s in run.stages]
    updated = replace(run, stages=tuple(new_stages))
    await store.update(updated)

    # Record version
    version = ReportVersionService.add_version(request, run_id, stage_id, body.content, body.editor)

    await dispatch_event(
        request,
        StageReportEdited(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "editor": body.editor,
                "version": version["version"],
            }
        ),
        stream_id=f"run:{run_id}",
    )

    return {
        "stage_id": stage_id,
        "report_key": rkey,
        "version": version["version"],
        "content": body.content,
    }


@router.get("/pipelines/{run_id}/stages/{stage_id}/report/versions")
async def list_report_versions(
    run_id: str,
    stage_id: str,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> list[dict[str, object]]:
    """List all versions of a stage report."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    return ReportVersionService.get_versions(request, run_id, stage_id)


@router.post("/pipelines/{run_id}/stages/{stage_id}/regenerate")
async def regenerate_stage(
    run_id: str,
    stage_id: str,
    body: RegeneratePayload,
    request: Request,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Re-run a stage with optional guidance, resetting it to running."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
    if status not in ("succeeded", "waiting_approval", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regenerate stage in '{status}' state",
        )

    # Store guidance in stage inputs for the node to pick up
    now = datetime.now(UTC).isoformat()
    inputs = dict(stage.inputs) if stage.inputs else {}
    if body.guidance:
        inputs["regenerate_guidance"] = body.guidance

    new_stages = [
        replace(
            s,
            status=StageStatus.RUNNING,
            started_at=now,
            finished_at="",
            error="",
            duration_ms=0,
            outputs=None,
            logs=(),
            inputs=inputs or None,
            retry_count=s.retry_count + 1,
        )
        if s.stage_id == stage_id
        else s
        for s in run.stages
    ]

    updated = replace(run, stages=tuple(new_stages), status=PipelineStatus.RUNNING)
    await store.update(updated)

    ReportVersionService.add_version(
        request,
        run_id,
        stage_id,
        f"[Regenerating: {body.guidance or 'no guidance'}]",
        "system",
        version_type="regenerate",
    )

    await dispatch_event(
        request,
        StageReportRegenerated(
            payload={
                "resource_id": stage_id,
                "run_id": run_id,
                "stage_name": stage.name,
                "guidance": body.guidance,
            }
        ),
        stream_id=f"run:{run_id}",
    )

    # Resume workflow execution for regeneration
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        task = asyncio.create_task(executor.resume(run_id))
        request.app.state._background_tasks = getattr(request.app.state, "_background_tasks", set())
        request.app.state._background_tasks.add(task)
        task.add_done_callback(request.app.state._background_tasks.discard)

    regen_stage = _find_stage(updated, stage_id)
    return asdict(regen_stage)  # type: ignore[arg-type]
