"""Test fixtures for ai-providers-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.ai_providers_api.routes import (
    ai_provider_store_provider,
    model_store_provider,
    router,
)
from lintel.ai_providers_api.store import InMemoryAIProviderStore

if TYPE_CHECKING:
    from collections.abc import Generator


class _InMemoryModelStore:
    """Minimal model store for testing list_provider_models."""

    def __init__(self) -> None:
        self._models: dict[str, object] = {}

    async def add(self, model: object) -> None:
        from dataclasses import asdict

        d = asdict(model)  # type: ignore[call-overload]
        self._models[d["model_id"]] = model

    async def list_by_provider(self, provider_id: str) -> list[object]:
        from dataclasses import asdict

        return [
            m
            for m in self._models.values()
            if asdict(m).get("provider_id") == provider_id  # type: ignore[call-overload]
        ]


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryAIProviderStore()
    m_store = _InMemoryModelStore()
    ai_provider_store_provider.override(store)
    model_store_provider.override(m_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    ai_provider_store_provider.override(None)
    model_store_provider.override(None)
