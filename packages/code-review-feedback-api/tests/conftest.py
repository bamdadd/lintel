"""Test fixtures for code-review-feedback-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.code_review_feedback_api.routes import review_comment_store_provider, router
from lintel.code_review_feedback_api.store import ReviewCommentStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    review_comment_store_provider.override(ReviewCommentStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    review_comment_store_provider.override(None)
