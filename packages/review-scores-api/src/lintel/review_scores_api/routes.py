"""Review scores API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.review_events import ReviewScoreRecorded

if TYPE_CHECKING:
    from lintel.review_scores_api.store import ReviewScoreStore

router = APIRouter()
review_score_store_provider: StoreProvider[ReviewScoreStore] = StoreProvider()


class CreateReviewScoreRequest(BaseModel, frozen=True):
    """Request to record a review score."""

    score_id: str = Field(default_factory=lambda: str(uuid4()))
    repo_id: str
    contributor_id: str = ""
    pipeline_run_id: str = ""
    dimension: str
    score: float
    severity: str = "info"


@router.post("/review-scores", status_code=201)
async def create_review_score(
    request: Request,
    body: CreateReviewScoreRequest,
    store: ReviewScoreStore = Depends(review_score_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Record a new review score."""
    from datetime import UTC, datetime

    data = body.model_dump()
    data["recorded_at"] = datetime.now(UTC).isoformat()
    await store.add(data)
    await dispatch_event(
        request,
        ReviewScoreRecorded(
            payload={
                "score_id": body.score_id,
                "repo_id": body.repo_id,
                "dimension": body.dimension,
                "score": body.score,
            },
        ),
        stream_id=f"review-score:{body.score_id}",
    )
    result = await store.get(body.score_id)
    return result  # type: ignore[return-value]


@router.get("/repositories/{repo_id}/review-scores/trends")
async def get_repo_score_trends(
    repo_id: str,
    dimension: str | None = None,
    store: ReviewScoreStore = Depends(review_score_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get review score trends for a repository."""
    return await store.get_trend_by_repo(repo_id, dimension=dimension)


@router.get("/contributors/{contributor_id}/review-scores/trends")
async def get_contributor_score_trends(
    contributor_id: str,
    dimension: str | None = None,
    store: ReviewScoreStore = Depends(review_score_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get review score trends for a contributor."""
    return await store.get_trend_by_contributor(contributor_id, dimension=dimension)
