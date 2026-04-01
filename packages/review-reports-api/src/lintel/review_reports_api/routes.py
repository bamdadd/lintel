"""Review reports API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.review_events import ReviewCompleted

if TYPE_CHECKING:
    from lintel.review_reports_api.store import ReviewReportStore

router = APIRouter()
review_report_store_provider: StoreProvider[ReviewReportStore] = StoreProvider()


class CreateReviewReportRequest(BaseModel, frozen=True):
    """Request to create a review report."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_run_id: str
    repo_id: str
    contributor_id: str = ""
    commit_shas: list[str] = Field(default_factory=list)
    per_file_scores: list[dict[str, Any]] = Field(default_factory=list)
    aggregate_scores: dict[str, float] = Field(default_factory=dict)
    storage_backend: str = "postgres"


@router.post("/review-reports", status_code=201)
async def create_review_report(
    request: Request,
    body: CreateReviewReportRequest,
    store: ReviewReportStore = Depends(review_report_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a new review report."""
    data = body.model_dump()
    await store.add(data)
    await dispatch_event(
        request,
        ReviewCompleted(
            payload={
                "report_id": body.report_id,
                "repo_id": body.repo_id,
                "pipeline_run_id": body.pipeline_run_id,
            },
        ),
        stream_id=f"review-report:{body.report_id}",
    )
    result = await store.get(body.report_id)
    return result  # type: ignore[return-value]


@router.get("/review-reports/{report_id}")
async def get_review_report(
    report_id: str,
    store: ReviewReportStore = Depends(review_report_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a review report by ID."""
    item = await store.get(report_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review report not found")
    return item


@router.get("/repositories/{repo_id}/review-reports")
async def list_review_reports_by_repo(
    repo_id: str,
    store: ReviewReportStore = Depends(review_report_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List review reports for a repository."""
    return await store.list_by_repo(repo_id)
