"""Test fixtures for agent-definitions-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.agent_definitions_api.routes import router, agent_definition_store_provider
from lintel.agent_definitions_api.store import AgentDefinitionStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    agent_definition_store_provider.override(AgentDefinitionStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    agent_definition_store_provider.override(None)
