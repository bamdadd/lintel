"""Work-item CRUD endpoints."""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.contracts.types import ThreadRef
from lintel.domain.events import WorkItemCreated, WorkItemRemoved, WorkItemUpdated
from lintel.domain.types import (
    Trigger,
    TriggerType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from lintel.persistence.data_models import WorkItemData
from lintel.work_items_api.store import WorkItemStore
from lintel.workflows.types import (
    PipelineRun,
    PipelineStatus,
    Stage,
)

logger = logging.getLogger(__name__)

router = APIRouter()

work_item_store_provider = StoreProvider()


class CreateWorkItemRequest(BaseModel):
    work_item_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    description: str = ""
    work_type: WorkItemType = WorkItemType.TASK
    status: WorkItemStatus = WorkItemStatus.OPEN
    assignee_agent_role: str = ""
    thread_ref_str: str = ""
    branch_name: str = ""
    pr_url: str = ""


class UpdateWorkItemRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    work_type: WorkItemType | None = None
    status: WorkItemStatus | None = None
    assignee_agent_role: str | None = None
    thread_ref_str: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    column_id: str | None = None
    column_position: int | None = None
    tags: list[str] | None = None


@router.post("/work-items", status_code=201)
async def create_work_item(
    body: CreateWorkItemRequest,
    request: Request,
    store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.work_item_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Work item already exists")
    work_item = WorkItem(
        work_item_id=body.work_item_id,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        work_type=body.work_type,
        status=body.status,
        assignee_agent_role=body.assignee_agent_role,
        thread_ref_str=body.thread_ref_str,
        branch_name=body.branch_name,
        pr_url=body.pr_url,
    )
    await store.add(work_item)
    await dispatch_event(
        request,
        WorkItemCreated(
            payload={
                "resource_id": body.work_item_id,
                "title": body.title,
                "project_id": body.project_id,
            }
        ),
        stream_id=f"work_item:{body.work_item_id}",
    )
    result = await store.get(body.work_item_id)
    return result  # type: ignore[return-value]


@router.get("/work-items")
async def list_work_items(
    project_id: Annotated[str | None, Query()] = None,
    store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all(project_id=project_id)


@router.get("/work-items/{work_item_id}")
async def get_work_item(
    work_item_id: str,
    store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item


@router.patch("/work-items/{work_item_id}")
async def update_work_item(
    work_item_id: str,
    body: UpdateWorkItemRequest,
    request: Request,
    store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(work_item_id, merged)
    await dispatch_event(
        request,
        WorkItemUpdated(payload={"resource_id": work_item_id, "fields": list(updates.keys())}),
        stream_id=f"work_item:{work_item_id}",
    )

    # Trigger workflow when status transitions to in_progress
    old_status = item.get("status", "")
    new_status = updates.get("status", "")
    if new_status == "in_progress" and old_status != "in_progress":
        # Enforce WIP limit before allowing transition
        project_id = item.get("project_id", "")
        wip_error = await _check_wip_limit(request, store, project_id, "in_progress")
        if wip_error:
            raise HTTPException(status_code=409, detail=wip_error)
        await _trigger_workflow_for_work_item(request, merged, work_item_id)

    # Auto-promote: when an item leaves in_progress, check if we should promote another
    if old_status == "in_progress" and new_status and new_status != "in_progress":
        project_id = item.get("project_id", "")
        await _auto_promote_open_items(request, store, project_id)

    result = await store.get(work_item_id)
    return result  # type: ignore[return-value]


async def _check_wip_limit(
    request: Request,
    store: WorkItemStore,
    project_id: str,
    target_status: str,
) -> str | None:
    """Check if the WIP limit for a board column would be exceeded.

    Returns an error message if the limit is reached, or None if OK.
    """
    if not project_id:
        return None

    board_store = getattr(request.app.state, "board_store", None)
    if board_store is None:
        return None

    try:
        boards = await board_store.list_by_project(project_id)
    except Exception:
        return None

    # Find the column matching the target status
    for board in boards:
        if isinstance(board, dict):
            columns: list[dict[str, object]] = board.get("columns", [])
        else:
            columns = list(getattr(board, "columns", ()))
        for col in columns:
            if isinstance(col, dict):
                col_status = str(col.get("work_item_status", ""))
                wip_limit = int(col.get("wip_limit", 0))  # type: ignore[call-overload]
                col_name = str(col.get("name", ""))
            else:
                col_status = getattr(col, "work_item_status", "")
                wip_limit = getattr(col, "wip_limit", 0)
                col_name = getattr(col, "name", "")

            if col_status == target_status and wip_limit > 0:
                all_items = await store.list_all(project_id=project_id)
                current_count = sum(1 for i in all_items if i.get("status") == target_status)
                if current_count >= wip_limit:
                    return (
                        f"WIP limit reached for '{col_name}': "
                        f"{current_count}/{wip_limit} items. "
                        f"Complete or move existing items before "
                        f"adding more."
                    )
    return None


async def _auto_promote_open_items(
    request: Request,
    store: WorkItemStore,
    project_id: str,
) -> None:
    """If auto_move is on and WIP has capacity, promote the oldest open item."""
    if not project_id:
        return
    board_store = getattr(request.app.state, "board_store", None)
    if board_store is None:
        return
    try:
        boards = await board_store.list_by_project(project_id)
    except Exception:
        return

    # Check if any board has auto_move enabled
    auto_move = any(
        (b.get("auto_move", False) if isinstance(b, dict) else getattr(b, "auto_move", False))
        for b in boards
    )
    if not auto_move:
        return

    # Find WIP limit for in_progress column
    wip_limit = 0
    for board in boards:
        columns = (
            board.get("columns", []) if isinstance(board, dict) else getattr(board, "columns", ())
        )
        for col in columns:
            col_status = (
                col.get("work_item_status", "")
                if isinstance(col, dict)
                else getattr(col, "work_item_status", "")
            )
            if col_status == "in_progress":
                wip_limit = int(
                    col.get("wip_limit", 0)
                    if isinstance(col, dict)
                    else getattr(col, "wip_limit", 0)
                )
                break

    all_items = await store.list_all(project_id=project_id)
    in_progress_count = sum(1 for i in all_items if i.get("status") == "in_progress")

    if wip_limit != 0 and in_progress_count >= wip_limit:
        return

    open_items = [i for i in all_items if i.get("status") == "open"]
    if not open_items:
        return

    # Pick the item at the top of the board column (lowest position)
    open_items.sort(key=lambda i: i.get("column_position", 0))
    candidate = open_items[0]
    candidate_id = candidate.get("work_item_id", "")
    if not candidate_id:
        return

    candidate["status"] = "in_progress"
    await store.update(candidate_id, candidate)
    logger.info("auto_promote_to_in_progress: %s", candidate_id)

    await dispatch_event(
        request,
        WorkItemUpdated(
            payload={
                "resource_id": candidate_id,
                "fields": ["status"],
                "auto_promoted": True,
            },
        ),
        stream_id=f"work_item:{candidate_id}",
    )
    # Trigger the workflow for the promoted item
    await _trigger_workflow_for_work_item(request, candidate, candidate_id)


async def _trigger_workflow_for_work_item(
    request: Request,
    item: dict[str, Any],
    work_item_id: str,
) -> None:
    """Dispatch a workflow when a work item moves to in_progress."""
    from lintel.workflows.commands import StartWorkflow

    project_id = item.get("project_id", "")
    if not project_id:
        return

    work_type = item.get("work_type", "task")
    workflow_type = {
        "feature": "feature_to_pr",
        "bug": "feature_to_pr",
        "refactor": "feature_to_pr",
        "task": "feature_to_pr",
    }.get(work_type, "feature_to_pr")

    # Check if the workflow is enabled
    defs_store = getattr(request.app.state, "workflow_definitions", None)
    if defs_store is not None:
        wf = defs_store.get(workflow_type)
        if wf is not None and not wf.get("enabled", True):
            logger.info("workflow_disabled_skipping_trigger: %s", workflow_type)
            return

    run_id = uuid4().hex
    trigger_id = uuid4().hex
    thread_ref = ThreadRef(
        workspace_id="board",
        channel_id="kanban",
        thread_ts=work_item_id,
    )

    # Create trigger
    trigger_store = getattr(request.app.state, "trigger_store", None)
    if trigger_store:
        trigger = Trigger(
            trigger_id=trigger_id,
            project_id=project_id,
            trigger_type=TriggerType.WORK_ITEM,
            name=f"work_item:{work_item_id}",
        )
        try:
            await trigger_store.add(trigger)
        except Exception:
            logger.warning("trigger_creation_failed", exc_info=True)

    # Create pipeline run
    pipeline_store = getattr(request.app.state, "pipeline_store", None)
    if pipeline_store:
        from lintel.api.routes.pipelines import _stage_names_for_workflow  # type: ignore[attr-defined]

        stage_names = _stage_names_for_workflow(workflow_type)
        stages = tuple(
            Stage(stage_id=uuid4().hex, name=name, stage_type=name) for name in stage_names
        )
        pipeline_run = PipelineRun(
            run_id=run_id,
            project_id=project_id,
            work_item_id=work_item_id,
            workflow_definition_id=workflow_type,
            status=PipelineStatus.RUNNING,
            trigger_type=f"work_item:{work_item_id}",
            trigger_id=trigger_id,
            stages=stages,
            created_at=datetime.now(UTC).isoformat(),
        )
        try:
            await pipeline_store.add(pipeline_run)
        except Exception:
            logger.warning("pipeline_run_creation_failed", exc_info=True)

    # Resolve repo context from project
    project_store = getattr(request.app.state, "project_store", None)
    repo_store = getattr(request.app.state, "repository_store", None)
    repo_url = ""
    repo_urls: tuple[str, ...] = ()
    repo_branch = "main"
    credential_ids: tuple[str, ...] = ()
    if project_store:
        try:
            project = await project_store.get(project_id)
            if project:
                repo_branch = project.get("default_branch", "main")
                credential_ids = tuple(project.get("credential_ids", ()))
                repo_ids = project.get("repo_ids", ())
                if isinstance(repo_ids, (list, tuple)) and repo_ids and repo_store:
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
            pass

    # Find most recent failed pipeline for continuation
    continue_from_run_id = ""
    if pipeline_store:
        try:
            all_runs = await pipeline_store.list_all()
            failed_runs = [
                r
                for r in all_runs
                if (
                    (r.work_item_id if hasattr(r, "work_item_id") else r.get("work_item_id", ""))
                    == work_item_id
                    and str(r.status if hasattr(r, "status") else r.get("status", ""))
                    in ("failed", str(PipelineStatus.FAILED))
                )
            ]
            if failed_runs:
                failed_runs.sort(
                    key=lambda r: (
                        r.created_at if hasattr(r, "created_at") else r.get("created_at", "")
                    ),
                    reverse=True,
                )
                prev = failed_runs[0]
                continue_from_run_id = (
                    prev.run_id if hasattr(prev, "run_id") else prev.get("run_id", "")
                )
                logger.info("continuing_from_previous_run: %s", continue_from_run_id)
        except Exception:
            logger.warning("continuation_lookup_failed", exc_info=True)

    command = StartWorkflow(
        thread_ref=thread_ref,
        workflow_type=workflow_type,
        sanitized_messages=(item.get("description", item.get("title", "")),),
        project_id=project_id,
        work_item_id=work_item_id,
        run_id=run_id,
        repo_url=repo_url,
        repo_urls=repo_urls,
        repo_branch=repo_branch,
        credential_ids=credential_ids,
        continue_from_run_id=continue_from_run_id,
    )

    dispatcher = getattr(request.app.state, "command_dispatcher", None)
    if dispatcher:
        asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
        logger.info(
            "workflow_triggered_from_board",
            extra={
                "work_item_id": work_item_id,
                "workflow_type": workflow_type,
                "run_id": run_id,
            },
        )


@router.delete("/work-items/{work_item_id}", status_code=204)
async def remove_work_item(
    work_item_id: str,
    request: Request,
    store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> None:
    item = await store.get(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    await store.remove(work_item_id)
    await dispatch_event(
        request,
        WorkItemRemoved(payload={"resource_id": work_item_id, "title": item.get("title", "")}),
        stream_id=f"work_item:{work_item_id}",
    )
