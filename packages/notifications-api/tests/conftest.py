"""Test fixtures for notifications-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.notifications_api.routes import router, notification_rule_store_provider
from lintel.notifications_api.store import NotificationRuleStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = NotificationRuleStore()
    notification_rule_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    notification_rule_store_provider.override(None)
