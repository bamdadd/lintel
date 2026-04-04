"""Test fixtures for kernel-policy-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.kernel_policy_api.routes import kernel_policy_store_provider, router
from lintel.kernel_policy_api.store import InMemoryKernelPolicyStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryKernelPolicyStore()
    kernel_policy_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    kernel_policy_store_provider.override(None)
