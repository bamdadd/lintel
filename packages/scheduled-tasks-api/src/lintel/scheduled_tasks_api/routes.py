"""Scheduled task CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    ScheduledTaskCreated,
    ScheduledTaskRemoved,
    ScheduledTaskUpdated,
)
from lintel.scheduled_tasks_api.types import ScheduledTask, TaskType

if TYPE_CHECKING:
    from lintel.scheduled_tasks_api.store import InMemoryScheduledTaskStore

router = APIRouter()

scheduled_task_store_provider: StoreProvider = StoreProvider()


class CreateScheduledTaskRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    cron_expression: str
    task_type: TaskType
    description: str = ""
    config: dict[str, object] = {}
    enabled: bool = True


class UpdateScheduledTaskRequest(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    task_type: TaskType | None = None
    description: str | None = None
    config: dict[str, object] | None = None
    enabled: bool | None = None


def _task_to_dict(task: ScheduledTask) -> dict[str, Any]:
    data = asdict(task)
    if data["last_run_at"] is not None:
        data["last_run_at"] = data["last_run_at"].isoformat()
    if data["next_run_at"] is not None:
        data["next_run_at"] = data["next_run_at"].isoformat()
    data["created_at"] = data["created_at"].isoformat()
    return data


@router.post("/scheduled-tasks", status_code=201)
async def create_scheduled_task(
    body: CreateScheduledTaskRequest,
    request: Request,
    store: InMemoryScheduledTaskStore = Depends(scheduled_task_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Scheduled task already exists")
    task = ScheduledTask(
        id=body.id,
        project_id=body.project_id,
        name=body.name,
        cron_expression=body.cron_expression,
        task_type=body.task_type,
        description=body.description,
        config=body.config,
        enabled=body.enabled,
    )
    await store.add(task)
    await dispatch_event(
        request,
        ScheduledTaskCreated(payload={"resource_id": body.id, "name": body.name}),
        stream_id=f"scheduled-task:{body.id}",
    )
    return _task_to_dict(task)


@router.get("/scheduled-tasks")
async def list_scheduled_tasks(
    project_id: str | None = None,
    store: InMemoryScheduledTaskStore = Depends(scheduled_task_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if project_id:
        tasks = await store.list_by_project(project_id)
    else:
        tasks = await store.list_all()
    return [_task_to_dict(t) for t in tasks]


@router.get("/scheduled-tasks/{task_id}")
async def get_scheduled_task(
    task_id: str,
    store: InMemoryScheduledTaskStore = Depends(scheduled_task_store_provider),  # noqa: B008
) -> dict[str, Any]:
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return _task_to_dict(task)


@router.patch("/scheduled-tasks/{task_id}")
async def update_scheduled_task(
    task_id: str,
    body: UpdateScheduledTaskRequest,
    request: Request,
    store: InMemoryScheduledTaskStore = Depends(scheduled_task_store_provider),  # noqa: B008
) -> dict[str, Any]:
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    updates = body.model_dump(exclude_none=True)
    updated = ScheduledTask(**{**asdict(task), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        ScheduledTaskUpdated(payload={"resource_id": task_id, "fields": list(updates.keys())}),
        stream_id=f"scheduled-task:{task_id}",
    )
    return _task_to_dict(updated)


@router.delete("/scheduled-tasks/{task_id}", status_code=204)
async def delete_scheduled_task(
    task_id: str,
    request: Request,
    store: InMemoryScheduledTaskStore = Depends(scheduled_task_store_provider),  # noqa: B008
) -> None:
    task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    await store.remove(task_id)
    await dispatch_event(
        request,
        ScheduledTaskRemoved(payload={"resource_id": task_id, "name": task.name}),
        stream_id=f"scheduled-task:{task_id}",
    )
