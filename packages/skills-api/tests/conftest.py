"""Test fixtures for skills-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.skills_api.routes import router, skill_store_provider
from lintel.skills_api.store import InMemorySkillStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    skill_store_provider.override(InMemorySkillStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    skill_store_provider.override(None)
