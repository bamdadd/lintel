"""Code review comment endpoints."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.code_review_feedback_api.types import (
    ReviewComment,
    ReviewCommentStatus,
    ReviewSeverity,
)

if TYPE_CHECKING:
    from lintel.code_review_feedback_api.store import ReviewCommentStore

router = APIRouter()

review_comment_store_provider: StoreProvider[ReviewCommentStore] = StoreProvider()


class CreateReviewCommentRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_run_id: str
    file_path: str
    line_number: int
    comment: str
    severity: str = "info"
    suggestion: str = ""


class UpdateReviewCommentRequest(BaseModel):
    status: str | None = None
    comment: str | None = None
    suggestion: str | None = None


def _comment_to_dict(comment: ReviewComment) -> dict[str, Any]:
    data = asdict(comment)
    data["severity"] = comment.severity.value
    data["status"] = comment.status.value
    return data


@router.post("/review-comments", status_code=201)
async def create_review_comment(
    body: CreateReviewCommentRequest,
    store: ReviewCommentStore = Depends(review_comment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Review comment already exists")
    try:
        severity = ReviewSeverity(body.severity)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=400,
            detail=f"Invalid severity: {body.severity}. Must be info, warning, or error",
        )
    comment = ReviewComment(
        id=body.id,
        pipeline_run_id=body.pipeline_run_id,
        file_path=body.file_path,
        line_number=body.line_number,
        comment=body.comment,
        severity=severity,
        suggestion=body.suggestion,
    )
    await store.add(comment)
    return _comment_to_dict(comment)


@router.get("/review-comments")
async def list_review_comments(
    pipeline_run_id: str | None = None,
    store: ReviewCommentStore = Depends(review_comment_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    comments = await store.list_all(pipeline_run_id=pipeline_run_id)
    return [_comment_to_dict(c) for c in comments]


@router.get("/review-comments/{comment_id}")
async def get_review_comment(
    comment_id: str,
    store: ReviewCommentStore = Depends(review_comment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    comment = await store.get(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Review comment not found")
    return _comment_to_dict(comment)


@router.patch("/review-comments/{comment_id}")
async def update_review_comment(
    comment_id: str,
    body: UpdateReviewCommentRequest,
    store: ReviewCommentStore = Depends(review_comment_store_provider),  # noqa: B008
) -> dict[str, Any]:
    comment = await store.get(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Review comment not found")

    updates: dict[str, Any] = {}

    if body.status is not None:
        try:
            updates["status"] = ReviewCommentStatus(body.status)
        except ValueError:
            raise HTTPException(  # noqa: B904
                status_code=400,
                detail=f"Invalid status: {body.status}. Must be open, resolved, or dismissed",
            )

    if body.comment is not None:
        updates["comment"] = body.comment

    if body.suggestion is not None:
        updates["suggestion"] = body.suggestion

    updated = replace(comment, **updates)
    await store.update(updated)
    return _comment_to_dict(updated)
