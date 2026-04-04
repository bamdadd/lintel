"""Test fixtures for release-notes-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.release_notes_api.routes import (
    release_note_store_provider,
    repo_provider_provider,
    router,
)
from lintel.release_notes_api.store import InMemoryReleaseNoteStore

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_mock_provider(prs: list[dict[str, Any]] | None = None) -> AsyncMock:
    mock = AsyncMock()
    mock.list_pull_requests.return_value = prs or []
    return mock


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryReleaseNoteStore()
    release_note_store_provider.override(store)
    repo_provider_provider.override(_make_mock_provider())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    release_note_store_provider.override(None)
    repo_provider_provider.override(None)


@pytest.fixture()
def client_with_prs() -> Generator[TestClient]:
    """Client with a repo provider that returns sample merged PRs."""
    prs = [
        {"number": 10, "title": "feat: add user auth"},
        {"number": 11, "title": "fix: login redirect"},
        {"number": 12, "title": "chore: update deps"},
        {"number": 13, "title": "docs: add API guide"},
        {"number": 14, "title": "Bump version to 2.0"},
    ]
    store = InMemoryReleaseNoteStore()
    release_note_store_provider.override(store)
    repo_provider_provider.override(_make_mock_provider(prs))
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    release_note_store_provider.override(None)
    repo_provider_provider.override(None)
