"""Work-item CRUD endpoints."""

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.contracts.data_models import WorkItemData
from lintel.contracts.events import WorkItemCreated, WorkItemRemoved, WorkItemUpdated
from lintel.contracts.types import (
    PipelineRun,
    PipelineStatus,
    Stage,
    ThreadRef,
    Trigger,
    TriggerType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from lintel.domain.event_dispatcher import dispatch_event

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkItemStore:
    """In-memory work-item store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, work_item: WorkItem) -> None:
        data = asdict(work_item)
        validated = WorkItemData.model_validate(data)
        self._data[work_item.work_item_id] = validated.model_dump()

    async def get(self, work_item_id: str) -> dict[str, Any] | None:
        return self._data.get(work_item_id)

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        items = list(self._data.values())
        if project_id is not None:
            items = [i for i in items if i["project_id"] == project_id]
        return items

    async def update(self, work_item_id: str, data: dict[str, Any]) -> None:
        validated = WorkItemData.model_validate(data)
        self._data[work_item_id] = validated.model_dump()

    async def remove(self, work_item_id: str) -> None:
        self._data.pop(work_item_id, None)


def get_work_item_store(request: Request) -> WorkItemStore:
    """Get work-item store from app state."""
    return request.app.state.work_item_store  # type: ignore[no-any-return]


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
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
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
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
    project_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    return await store.list_all(project_id=project_id)


@router.get("/work-items/{work_item_id}")
async def get_work_item(
    work_item_id: str,
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
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
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
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
        await _trigger_workflow_for_work_item(request, merged, work_item_id)

    result = await store.get(work_item_id)
    return result  # type: ignore[return-value]


async def _trigger_workflow_for_work_item(
    request: Request,
    item: dict[str, Any],
    work_item_id: str,
) -> None:
    """Dispatch a workflow when a work item moves to in_progress."""
    from lintel.api.routes.pipelines import _stage_names_for_workflow
    from lintel.contracts.commands import StartWorkflow

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
    from lintel.api.routes.workflow_definitions import get_workflow_defs

    defs = get_workflow_defs(request)
    wf = defs.get(workflow_type)
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
            trigger_type=TriggerType.MANUAL,
            name=f"board:{work_item_id}",
        )
        try:
            await trigger_store.add(trigger)
        except Exception:
            logger.warning("trigger_creation_failed", exc_info=True)

    # Create pipeline run
    pipeline_store = getattr(request.app.state, "pipeline_store", None)
    if pipeline_store:
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
            trigger_type=f"board:{work_item_id}",
            trigger_id=trigger_id,
            stages=stages,
            created_at=datetime.now(UTC).isoformat(),
        )
        try:
            await pipeline_store.add(pipeline_run)
        except Exception:
            logger.warning("pipeline_run_creation_failed", exc_info=True)

    # Resolve repo context from project — look up repo_ids to get actual URLs
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
                # Resolve repo IDs to URLs (same logic as chat route)
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
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
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
