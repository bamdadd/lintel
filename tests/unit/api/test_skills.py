"""Tests for the skill API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app

SKILL_BODY = {
    "skill_id": "s1",
    "name": "echo-skill",
    "version": "1.0.0",
}


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestSkillsAPI:
    def test_register_skill(self, client: TestClient) -> None:
        resp = client.post("/api/v1/skills", json=SKILL_BODY)
        assert resp.status_code == 201
        data = resp.json()
        assert data["skill_id"] == "s1"
        assert data["name"] == "echo-skill"
        assert data["version"] == "1.0.0"

    def test_register_duplicate_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/skills", json=SKILL_BODY)
        resp = client.post("/api/v1/skills", json=SKILL_BODY)
        assert resp.status_code == 409

    def test_list_skills_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/skills")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_skills_after_registration(self, client: TestClient) -> None:
        client.post("/api/v1/skills", json=SKILL_BODY)
        resp = client.get("/api/v1/skills")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["skill_id"] == "s1"

    def test_invoke_skill(self, client: TestClient) -> None:
        client.post("/api/v1/skills", json=SKILL_BODY)
        resp = client.post(
            "/api/v1/skills/s1/invoke",
            json={"input_data": {"msg": "hi"}, "context": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_invoke_nonexistent_skill_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/skills/nonexistent/invoke",
            json={"input_data": {}, "context": {}},
        )
        assert resp.status_code == 404
