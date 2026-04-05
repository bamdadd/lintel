"""Browser extension component modification endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.browser_extension_api.store import InMemoryComponentModificationStore  # noqa: TC001
from lintel.browser_extension_api.types import ComponentModification, ModificationStatus
from lintel.domain.events import (
    ComponentModificationCompleted,
    ComponentModificationRequested,
)

router = APIRouter()

modification_store_provider: StoreProvider[InMemoryComponentModificationStore] = StoreProvider()


class CreateModificationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    component_path: str
    instructions: str
    screenshot_url: str = ""
    selector: str = ""
    page_url: str = ""


class UpdateModificationRequest(BaseModel):
    status: ModificationStatus | None = None
    preview_url: str | None = None
    diff: str | None = None
    error_message: str | None = None


@router.post("/browser-extension/modifications", status_code=201)
async def create_modification(
    request: Request,
    body: CreateModificationRequest,
    store: Annotated[InMemoryComponentModificationStore, Depends(modification_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Component modification already exists")
    modification = ComponentModification(
        id=body.id,
        project_id=body.project_id,
        component_path=body.component_path,
        instructions=body.instructions,
        screenshot_url=body.screenshot_url,
        selector=body.selector,
        page_url=body.page_url,
    )
    result = await store.add(modification)
    await dispatch_event(
        request,
        ComponentModificationRequested(
            payload={
                "resource_id": body.id,
                "project_id": body.project_id,
                "component_path": body.component_path,
            },
        ),
        stream_id=f"component-modification:{body.id}",
    )
    return result


@router.get("/browser-extension/modifications")
async def list_modifications(
    store: Annotated[InMemoryComponentModificationStore, Depends(modification_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/browser-extension/modifications/{modification_id}")
async def get_modification(
    modification_id: str,
    store: Annotated[InMemoryComponentModificationStore, Depends(modification_store_provider)],
) -> dict[str, Any]:
    item = await store.get(modification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Component modification not found")
    return item


@router.patch("/browser-extension/modifications/{modification_id}")
async def update_modification(
    request: Request,
    modification_id: str,
    body: UpdateModificationRequest,
    store: Annotated[InMemoryComponentModificationStore, Depends(modification_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(modification_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Component modification not found")
    if body.status in {ModificationStatus.APPLIED, ModificationStatus.FAILED}:
        await dispatch_event(
            request,
            ComponentModificationCompleted(
                payload={
                    "resource_id": modification_id,
                    "status": body.status.value,
                },
            ),
            stream_id=f"component-modification:{modification_id}",
        )
    return result


@router.delete("/browser-extension/modifications/{modification_id}", status_code=204)
async def delete_modification(
    modification_id: str,
    store: Annotated[InMemoryComponentModificationStore, Depends(modification_store_provider)],
) -> None:
    if not await store.remove(modification_id):
        raise HTTPException(status_code=404, detail="Component modification not found")
