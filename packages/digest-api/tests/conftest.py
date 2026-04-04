"""Test fixtures for digest-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.digest_api.routes import (
    digest_config_store_provider,
    digest_store_provider,
    pipeline_store_provider,
    router,
    work_item_store_provider,
)
from lintel.digest_api.store import InMemoryDigestConfigStore, InMemoryDigestStore

if TYPE_CHECKING:
    from collections.abc import Generator


class FakeWorkItemStore:
    """Fake work-item store for testing digest generation."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id is not None:
            return [i for i in self.items if i.get("project_id") == project_id]
        return list(self.items)


class FakePipelineStore:
    """Fake pipeline store for testing digest generation."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id is not None:
            return [i for i in self.items if i.get("project_id") == project_id]
        return list(self.items)


@pytest.fixture()
def wi_store() -> FakeWorkItemStore:
    return FakeWorkItemStore()


@pytest.fixture()
def pl_store() -> FakePipelineStore:
    return FakePipelineStore()


@pytest.fixture()
def client(
    wi_store: FakeWorkItemStore,
    pl_store: FakePipelineStore,
) -> Generator[TestClient]:
    digest_store = InMemoryDigestStore()
    config_store = InMemoryDigestConfigStore()
    digest_store_provider.override(digest_store)
    digest_config_store_provider.override(config_store)
    work_item_store_provider.override(wi_store)
    pipeline_store_provider.override(pl_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    digest_store_provider.override(None)
    digest_config_store_provider.override(None)
    work_item_store_provider.override(None)
    pipeline_store_provider.override(None)
