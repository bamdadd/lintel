"""Test fixtures for secret-rotation-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.secret_rotation_api.routes import (
    expiry_tracker_provider,
    rotation_history_store_provider,
    rotation_policy_store_provider,
    router,
)
from lintel.secret_rotation_api.store import (
    InMemoryExpiryTracker,
    InMemoryRotationHistoryStore,
    InMemoryRotationPolicyStore,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    policy_store = InMemoryRotationPolicyStore()
    history_store = InMemoryRotationHistoryStore()
    expiry_tracker = InMemoryExpiryTracker()
    rotation_policy_store_provider.override(policy_store)
    rotation_history_store_provider.override(history_store)
    expiry_tracker_provider.override(expiry_tracker)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    rotation_policy_store_provider.override(None)
    rotation_history_store_provider.override(None)
    expiry_tracker_provider.override(None)
