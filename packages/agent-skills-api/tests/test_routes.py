"""Tests for agent skills API (REQ-F033)."""

from fastapi.testclient import TestClient


class TestAgentSkillsAPI:
    def test_list_categories(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-skills/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert "code_generation" in cats
        assert "custom" in cats
        assert len(cats) == 9

    def test_create_skill_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/agent-skills",
            json={
                "skill_id": "sk-1",
                "name": "Code Review",
                "category": "code_review",
                "required_tools": ["sandbox_read_file"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["skill_id"] == "sk-1"
        assert data["name"] == "Code Review"
        assert data["category"] == "code_review"
        assert data["required_tools"] == ["sandbox_read_file"]
        assert data["active"] is True

    def test_list_skills_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-skills")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_skill_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-skills",
            json={"skill_id": "sk-2", "name": "Testing"},
        )
        resp = client.get("/api/v1/agent-skills/sk-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Testing"

    def test_get_skill_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-skills/nonexistent")
        assert resp.status_code == 404

    def test_update_skill(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-skills",
            json={"skill_id": "sk-3", "name": "Docs"},
        )
        resp = client.patch(
            "/api/v1/agent-skills/sk-3",
            json={"name": "Documentation", "category": "documentation"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Documentation"
        assert resp.json()["category"] == "documentation"

    def test_update_skill_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/agent-skills/nonexistent",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_skill(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-skills",
            json={"skill_id": "sk-4", "name": "Deploy"},
        )
        resp = client.delete("/api/v1/agent-skills/sk-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/agent-skills/sk-4").status_code == 404

    def test_delete_skill_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/agent-skills/nonexistent")
        assert resp.status_code == 404


class TestAgentSkillBindingsAPI:
    def test_create_binding_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/agent-skills/bindings",
            json={
                "binding_id": "bind-1",
                "agent_definition_id": "agent-1",
                "skill_id": "sk-1",
                "priority": 10,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["binding_id"] == "bind-1"
        assert data["agent_definition_id"] == "agent-1"
        assert data["skill_id"] == "sk-1"
        assert data["priority"] == 10

    def test_list_bindings_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-skills/bindings")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_binding(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-skills/bindings",
            json={
                "binding_id": "bind-2",
                "agent_definition_id": "agent-1",
                "skill_id": "sk-1",
            },
        )
        resp = client.delete("/api/v1/agent-skills/bindings/bind-2")
        assert resp.status_code == 204

    def test_delete_binding_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/agent-skills/bindings/nonexistent")
        assert resp.status_code == 404

    def test_list_skills_for_agent(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-skills/bindings",
            json={
                "binding_id": "bind-3",
                "agent_definition_id": "agent-A",
                "skill_id": "sk-1",
            },
        )
        client.post(
            "/api/v1/agent-skills/bindings",
            json={
                "binding_id": "bind-4",
                "agent_definition_id": "agent-B",
                "skill_id": "sk-2",
            },
        )
        resp = client.get("/api/v1/agent-skills/agents/agent-A/skills")
        assert resp.status_code == 200
        bindings = resp.json()
        assert len(bindings) == 1
        assert bindings[0]["agent_definition_id"] == "agent-A"
