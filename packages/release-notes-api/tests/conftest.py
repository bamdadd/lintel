"""Test fixtures for release-notes-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.release_notes_api.routes import release_note_store_provider, router
from lintel.release_notes_api.store import InMemoryReleaseNoteStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryReleaseNoteStore()
    release_note_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    release_note_store_provider.override(None)
