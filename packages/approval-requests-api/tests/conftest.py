"""Test fixtures for approval-requests-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.approval_requests_api.routes import router, approval_request_store_provider
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryApprovalRequestStore()
    approval_request_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    approval_request_store_provider.override(None)
