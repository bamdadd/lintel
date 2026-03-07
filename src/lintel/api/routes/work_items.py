"""Work-item CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from lintel.contracts.types import WorkItem, WorkItemStatus, WorkItemType

router = APIRouter()


class WorkItemStore:
    """In-memory work-item store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, work_item: WorkItem) -> None:
        self._data[work_item.work_item_id] = asdict(work_item)

    async def get(self, work_item_id: str) -> dict[str, Any] | None:
        return self._data.get(work_item_id)

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        items = list(self._data.values())
        if project_id is not None:
            items = [i for i in items if i["project_id"] == project_id]
        return items

    async def update(self, work_item_id: str, data: dict[str, Any]) -> None:
        self._data[work_item_id] = data

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


@router.post("/work-items", status_code=201)
async def create_work_item(
    body: CreateWorkItemRequest,
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
    return asdict(work_item)


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
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
) -> dict[str, Any]:
    item = await store.get(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(work_item_id, merged)
    return merged


@router.delete("/work-items/{work_item_id}", status_code=204)
async def remove_work_item(
    work_item_id: str,
    store: Annotated[WorkItemStore, Depends(get_work_item_store)],
) -> None:
    item = await store.get(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    await store.remove(work_item_id)
