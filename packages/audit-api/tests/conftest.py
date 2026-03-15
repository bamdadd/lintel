"""Test fixtures for audit-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.audit_api.routes import router, audit_entry_store_provider
from lintel.audit_api.store import AuditEntryStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = AuditEntryStore()
    audit_entry_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    audit_entry_store_provider.override(None)
