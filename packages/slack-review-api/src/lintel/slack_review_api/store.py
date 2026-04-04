"""In-memory store for slack review requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SlackReviewRequest:
    """A PR review request triggered from Slack."""

    review_id: str
    repo_url: str
    pr_number: int
    slack_channel_id: str
    slack_thread_ts: str
    slack_user_id: str
    status: str = "pending"  # pending | reviewing | completed | failed
    verdict: str = ""
    review_body: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class InMemorySlackReviewStore:
    """Simple in-memory store for slack review requests."""

    def __init__(self) -> None:
        self._reviews: dict[str, SlackReviewRequest] = {}

    async def add(self, review: SlackReviewRequest) -> dict[str, Any]:
        self._reviews[review.review_id] = review
        from dataclasses import asdict

        return asdict(review)

    async def get(self, review_id: str) -> SlackReviewRequest | None:
        return self._reviews.get(review_id)

    async def update(self, review: SlackReviewRequest) -> None:
        self._reviews[review.review_id] = review

    async def list_all(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
    ) -> list[dict[str, Any]]:
        from dataclasses import asdict

        items = list(self._reviews.values())
        if status is not None:
            items = [r for r in items if r.status == status]
        if channel is not None:
            items = [r for r in items if r.slack_channel_id == channel]
        return [asdict(r) for r in items]
