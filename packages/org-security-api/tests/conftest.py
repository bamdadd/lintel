"""Test fixtures for org-security-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.org_security_api.routes import org_security_policy_store_provider, router
from lintel.org_security_api.store import InMemoryOrgSecurityPolicyStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryOrgSecurityPolicyStore()
    org_security_policy_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    org_security_policy_store_provider.override(None)
