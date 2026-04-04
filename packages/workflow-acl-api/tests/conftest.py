"""Test fixtures for workflow-acl-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.workflow_acl_api.routes import acl_rule_store_provider, router
from lintel.workflow_acl_api.store import InMemoryAclRuleStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    acl_rule_store_provider.override(InMemoryAclRuleStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    acl_rule_store_provider.override(None)
