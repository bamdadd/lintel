"""Product feedback CRUD endpoints (REQ-025)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    FeedbackCategorized,
    FeedbackReceived,
    FeedbackWorkItemCreated,
)
from lintel.feedback_api.store import InMemoryFeedbackStore  # noqa: TC001
from lintel.feedback_api.types import (
    FeedbackCategory,
    FeedbackPriority,
    FeedbackStatus,
    FeedbackTechnicalContext,
    ProductFeedback,
)

router = APIRouter()

feedback_store_provider: StoreProvider[InMemoryFeedbackStore] = StoreProvider()


class TechnicalContextRequest(BaseModel):
    browser: str = ""
    device: str = ""
    os: str = ""
    session_id: str = ""
    url: str = ""
    recent_changes: list[str] = []
    extra: dict[str, Any] = {}


class CreateFeedbackRequest(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    submitted_by: str = ""
    title: str
    body: str = ""
    category: FeedbackCategory = FeedbackCategory.OTHER
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    tags: list[str] = []
    technical_context: TechnicalContextRequest | None = None


class UpdateFeedbackRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    category: FeedbackCategory | None = None
    status: FeedbackStatus | None = None
    priority: FeedbackPriority | None = None
    tags: list[str] | None = None
    work_item_id: str | None = None


@router.post("/feedback", status_code=201)
async def create_feedback(
    request: Request,
    body: CreateFeedbackRequest,
    store: Annotated[InMemoryFeedbackStore, Depends(feedback_store_provider)],
) -> dict[str, Any]:
    existing = await store.get(body.feedback_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Feedback already exists")

    tc = FeedbackTechnicalContext()
    if body.technical_context is not None:
        tc = FeedbackTechnicalContext(
            browser=body.technical_context.browser,
            device=body.technical_context.device,
            os=body.technical_context.os,
            session_id=body.technical_context.session_id,
            url=body.technical_context.url,
            recent_changes=tuple(body.technical_context.recent_changes),
            extra=body.technical_context.extra,
        )

    feedback = ProductFeedback(
        feedback_id=body.feedback_id,
        project_id=body.project_id,
        submitted_by=body.submitted_by,
        title=body.title,
        body=body.body,
        category=body.category,
        priority=body.priority,
        tags=tuple(body.tags),
        technical_context=tc,
    )
    result = await store.add(feedback)
    await dispatch_event(
        request,
        FeedbackReceived(
            payload={"resource_id": body.feedback_id, "title": body.title},
        ),
        stream_id=f"feedback:{body.feedback_id}",
    )
    return result


@router.get("/feedback")
async def list_feedback(
    store: Annotated[InMemoryFeedbackStore, Depends(feedback_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/feedback/{feedback_id}")
async def get_feedback(
    feedback_id: str,
    store: Annotated[InMemoryFeedbackStore, Depends(feedback_store_provider)],
) -> dict[str, Any]:
    item = await store.get(feedback_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return item


@router.patch("/feedback/{feedback_id}")
async def update_feedback(
    request: Request,
    feedback_id: str,
    body: UpdateFeedbackRequest,
    store: Annotated[InMemoryFeedbackStore, Depends(feedback_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "tags" in updates:
        updates["tags"] = tuple(updates["tags"])
    result = await store.update(feedback_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    # Emit specific events based on what changed
    if body.category is not None:
        await dispatch_event(
            request,
            FeedbackCategorized(
                payload={
                    "resource_id": feedback_id,
                    "category": body.category.value,
                },
            ),
            stream_id=f"feedback:{feedback_id}",
        )
    if body.work_item_id is not None:
        await dispatch_event(
            request,
            FeedbackWorkItemCreated(
                payload={
                    "resource_id": feedback_id,
                    "work_item_id": body.work_item_id,
                },
            ),
            stream_id=f"feedback:{feedback_id}",
        )
    return result


@router.delete("/feedback/{feedback_id}", status_code=204)
async def delete_feedback(
    feedback_id: str,
    store: Annotated[InMemoryFeedbackStore, Depends(feedback_store_provider)],
) -> None:
    if not await store.remove(feedback_id):
        raise HTTPException(status_code=404, detail="Feedback not found")
