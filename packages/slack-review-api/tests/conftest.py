"""Test fixtures for slack-review-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.slack_review_api.routes import review_store_provider, router
from lintel.slack_review_api.store import InMemorySlackReviewStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def store() -> InMemorySlackReviewStore:
    return InMemorySlackReviewStore()


@pytest.fixture()
def mock_github() -> AsyncMock:
    gh = AsyncMock()
    gh.get_pr_diff = AsyncMock(return_value="diff --git a/foo.py b/foo.py\n+hello")
    gh.add_comment = AsyncMock()
    return gh


@pytest.fixture()
def client(store: InMemorySlackReviewStore, mock_github: AsyncMock) -> Generator[TestClient]:
    review_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.github_provider = mock_github
    with TestClient(app) as c:
        yield c
    review_store_provider.override(None)
