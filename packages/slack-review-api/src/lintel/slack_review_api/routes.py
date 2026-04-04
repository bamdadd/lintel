"""Slack review endpoints — trigger PR review from Slack."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.slack_review_api.handler import SlackReviewHandler, parse_pr_number
from lintel.slack_review_api.store import InMemorySlackReviewStore, SlackReviewRequest

logger = structlog.get_logger()

router = APIRouter()

review_store_provider: StoreProvider[InMemorySlackReviewStore] = StoreProvider()


class TriggerReviewRequest(BaseModel):
    """Request body for POST /slack/review."""

    repo_url: str
    pr_number: int | None = None
    slack_channel_id: str
    slack_thread_ts: str
    slack_user_id: str
    message_text: str = Field(
        default="",
        description="Original Slack message text; PR number is parsed if pr_number unset.",
    )


class ReviewResponse(BaseModel):
    """Response for a slack review trigger."""

    review_id: str
    status: str
    verdict: str
    review_body: str
    pr_number: int
    repo_url: str


@router.post("/slack/review", status_code=201)
async def trigger_review(
    body: TriggerReviewRequest,
    request: Request,
    store: InMemorySlackReviewStore = Depends(review_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Trigger a standalone PR review from Slack.

    Either ``pr_number`` is provided directly or it is parsed from
    ``message_text`` (e.g. "review PR #42").
    """
    pr_number = body.pr_number
    if pr_number is None:
        pr_number = parse_pr_number(body.message_text)
    if pr_number is None:
        raise HTTPException(
            status_code=422,
            detail="Could not determine PR number. "
            "Provide pr_number or include 'PR #N' in message_text.",
        )

    review_id = str(uuid4())
    review = SlackReviewRequest(
        review_id=review_id,
        repo_url=body.repo_url,
        pr_number=pr_number,
        slack_channel_id=body.slack_channel_id,
        slack_thread_ts=body.slack_thread_ts,
        slack_user_id=body.slack_user_id,
    )
    await store.add(review)

    # Dispatch domain event
    from lintel.domain.events import SlackReviewRequested

    await dispatch_event(
        request,
        SlackReviewRequested(
            payload={
                "resource_id": review_id,
                "pr_number": pr_number,
                "repo_url": body.repo_url,
                "slack_channel_id": body.slack_channel_id,
            },
        ),
        stream_id=f"slack-review:{review_id}",
    )

    # Run review synchronously (handler fetches diff, analyses, posts comment)
    github_provider = getattr(request.app.state, "github_provider", None)
    if github_provider is None:
        logger.warning("slack_review_no_github_provider")
        return asdict(review)

    handler = SlackReviewHandler(
        github_provider=github_provider,
        review_store=store,
    )
    result = await handler.run_review(review)

    # Post result back to Slack thread if adapter available
    slack_adapter = getattr(request.app.state, "slack_adapter", None)
    if slack_adapter is not None:
        try:
            from lintel.contracts.types import ThreadRef

            thread_ref = ThreadRef(
                workspace_id="",
                channel_id=body.slack_channel_id,
                thread_ts=body.slack_thread_ts,
            )
            await slack_adapter.send_message(
                thread_ref,
                handler.format_slack_message(result),
            )
        except Exception:
            logger.warning("slack_review_reply_failed", review_id=review_id)

    return result


@router.get("/slack/reviews")
async def list_reviews(
    store: InMemorySlackReviewStore = Depends(review_store_provider),  # noqa: B008
    status: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """List slack review requests."""
    return await store.list_all(status=status, channel=channel)


@router.get("/slack/reviews/{review_id}")
async def get_review(
    review_id: str,
    store: InMemorySlackReviewStore = Depends(review_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific slack review request."""
    review = await store.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Slack review not found")
    return asdict(review)
