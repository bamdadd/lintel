"""In-memory store for review comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.code_review_feedback_api.types import ReviewComment


class ReviewCommentStore:
    """In-memory store for review comments."""

    def __init__(self) -> None:
        self._comments: dict[str, ReviewComment] = {}

    async def add(self, comment: ReviewComment) -> None:
        self._comments[comment.id] = comment

    async def get(self, comment_id: str) -> ReviewComment | None:
        return self._comments.get(comment_id)

    async def update(self, comment: ReviewComment) -> None:
        self._comments[comment.id] = comment

    async def list_all(
        self,
        *,
        pipeline_run_id: str | None = None,
    ) -> list[ReviewComment]:
        comments = list(self._comments.values())
        if pipeline_run_id is not None:
            comments = [c for c in comments if c.pipeline_run_id == pipeline_run_id]
        return comments
