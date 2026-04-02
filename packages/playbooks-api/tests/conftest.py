"""Test fixtures for playbooks-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from lintel.playbooks_api.routes import playbook_store_provider, router
from lintel.playbooks_api.store import PlaybookStore


@pytest.fixture()
def client() -> Generator[TestClient, Any, None]:
    playbook_store_provider.override(PlaybookStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    playbook_store_provider.override(None)  # type: ignore[arg-type]
