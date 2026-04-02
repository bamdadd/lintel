"""Context attachment CRUD endpoints (REQ-027)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.context_attachments_api.store import InMemoryAttachmentStore  # noqa: TC001
from lintel.context_attachments_api.types import (
    Attachment,
    AttachmentTarget,
    AttachmentType,
)
from lintel.domain.events import (
    AttachmentLinked,
    AttachmentRemoved,
    AttachmentUploaded,
)

router = APIRouter()

attachment_store_provider: StoreProvider[InMemoryAttachmentStore] = StoreProvider()


class CreateAttachmentRequest(BaseModel):
    attachment_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    target_type: AttachmentTarget = AttachmentTarget.WORK_ITEM
    target_id: str = ""
    attachment_type: AttachmentType = AttachmentType.OTHER
    filename: str = ""
    url: str = ""
    description: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    tags: list[str] = []
    created_by: str = ""


class UpdateAttachmentRequest(BaseModel):
    description: str | None = None
    url: str | None = None
    filename: str | None = None
    attachment_type: AttachmentType | None = None
    target_type: AttachmentTarget | None = None
    target_id: str | None = None
    tags: list[str] | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


@router.post("/attachments", status_code=201)
async def create_attachment(
    request: Request,
    body: CreateAttachmentRequest,
    store: Annotated[InMemoryAttachmentStore, Depends(attachment_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.attachment_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Attachment already exists")

    attachment = Attachment(
        attachment_id=body.attachment_id,
        project_id=body.project_id,
        target_type=body.target_type,
        target_id=body.target_id,
        attachment_type=body.attachment_type,
        filename=body.filename,
        url=body.url,
        description=body.description,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        tags=tuple(body.tags),
        created_by=body.created_by,
    )
    result = await store.add(attachment)
    await dispatch_event(
        request,
        AttachmentUploaded(
            payload={"resource_id": body.attachment_id, "filename": body.filename},
        ),
        stream_id=f"attachment:{body.attachment_id}",
    )
    if body.target_id:
        await dispatch_event(
            request,
            AttachmentLinked(
                payload={
                    "resource_id": body.attachment_id,
                    "target_type": body.target_type.value,
                    "target_id": body.target_id,
                },
            ),
            stream_id=f"attachment:{body.attachment_id}",
        )
    return result


@router.get("/attachments")
async def list_attachments(
    store: Annotated[InMemoryAttachmentStore, Depends(attachment_store_provider)],
    project_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[dict[str, Any]]:
    if target_type and target_id:
        return await store.list_by_target(target_type, target_id)
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/attachments/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    store: Annotated[InMemoryAttachmentStore, Depends(attachment_store_provider)],
) -> dict[str, Any]:
    item = await store.get(attachment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return item


@router.patch("/attachments/{attachment_id}")
async def update_attachment(
    request: Request,
    attachment_id: str,
    body: UpdateAttachmentRequest,
    store: Annotated[InMemoryAttachmentStore, Depends(attachment_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "tags" in updates:
        updates["tags"] = tuple(updates["tags"])
    result = await store.update(attachment_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if body.target_id is not None:
        await dispatch_event(
            request,
            AttachmentLinked(
                payload={
                    "resource_id": attachment_id,
                    "target_type": body.target_type.value if body.target_type else "",
                    "target_id": body.target_id,
                },
            ),
            stream_id=f"attachment:{attachment_id}",
        )
    return result


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    request: Request,
    attachment_id: str,
    store: Annotated[InMemoryAttachmentStore, Depends(attachment_store_provider)],
) -> None:
    if not await store.remove(attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    await dispatch_event(
        request,
        AttachmentRemoved(payload={"resource_id": attachment_id}),
        stream_id=f"attachment:{attachment_id}",
    )
