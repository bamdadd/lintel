"""Test fixtures for slack-notifications-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.slack_notifications_api.routes import (
    record_store_provider,
    router,
    template_store_provider,
)
from lintel.slack_notifications_api.store import (
    InMemorySlackNotificationRecordStore,
    InMemorySlackNotificationTemplateStore,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    tpl_store = InMemorySlackNotificationTemplateStore()
    rec_store = InMemorySlackNotificationRecordStore()
    template_store_provider.override(tpl_store)
    record_store_provider.override(rec_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    template_store_provider.override(None)
    record_store_provider.override(None)
