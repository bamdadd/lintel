"""Test fixtures for agent-skills-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.agent_skills_api.routes import (
    agent_skill_binding_store_provider,
    agent_skill_store_provider,
    router,
)
from lintel.agent_skills_api.store import InMemoryAgentSkillBindingStore, InMemoryAgentSkillStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    skill_store = InMemoryAgentSkillStore()
    binding_store = InMemoryAgentSkillBindingStore()
    agent_skill_store_provider.override(skill_store)
    agent_skill_binding_store_provider.override(binding_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    agent_skill_store_provider.override(None)
    agent_skill_binding_store_provider.override(None)
