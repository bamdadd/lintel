"""Test fixtures for models-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.ai_providers_api.routes import (
    ai_provider_store_provider as ai_prov_store_provider,
)
from lintel.ai_providers_api.routes import (
    model_store_provider as ai_prov_model_store_provider,
)
from lintel.ai_providers_api.routes import (
    router as ai_providers_router,
)
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.models_api.routes import (
    ai_provider_store_provider,
    model_assignment_store_provider,
    model_store_provider,
    router,
)
from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryModelStore()
    assignment_store = InMemoryModelAssignmentStore()
    provider_store = InMemoryAIProviderStore()
    model_store_provider.override(store)
    model_assignment_store_provider.override(assignment_store)
    ai_provider_store_provider.override(provider_store)
    ai_prov_store_provider.override(provider_store)
    ai_prov_model_store_provider.override(store)
    app = FastAPI()
    app.include_router(ai_providers_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    model_store_provider.override(None)
    model_assignment_store_provider.override(None)
    ai_provider_store_provider.override(None)
    ai_prov_store_provider.override(None)
    ai_prov_model_store_provider.override(None)
