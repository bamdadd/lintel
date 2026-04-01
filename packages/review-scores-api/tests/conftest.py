"""Test fixtures for review-scores-api."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
import pytest

from lintel.review_scores_api.routes import review_score_store_provider, router
from lintel.review_scores_api.store import ReviewScoreStore

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> Generator[TestClient]:
    from fastapi.testclient import TestClient as _TClient

    review_score_store_provider.override(ReviewScoreStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with _TClient(app) as c:
        yield c
    review_score_store_provider.reset()
