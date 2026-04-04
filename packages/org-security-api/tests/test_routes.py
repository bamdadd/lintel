"""Tests for org-security-api endpoints."""

from fastapi.testclient import TestClient


class TestOrgSecurityAPI:
    def test_create_policy_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/org-policies",
            json={
                "policy_id": "pol-1",
                "name": "No sandbox network",
                "scope": "sandbox",
                "action": "deny",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "pol-1"
        assert data["name"] == "No sandbox network"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {"policy_id": "pol-dup", "name": "Dup", "scope": "agent", "action": "deny"}
        client.post("/api/v1/org-policies", json=body)
        resp = client.post("/api/v1/org-policies", json=body)
        assert resp.status_code == 409

    def test_list_empty_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/org-policies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/org-policies",
            json={"policy_id": "pol-2", "name": "P2", "scope": "agent", "action": "deny"},
        )
        resp = client.get("/api/v1/org-policies")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["policy_id"] == "pol-2"

    def test_list_filter_by_scope(self, client: TestClient) -> None:
        client.post(
            "/api/v1/org-policies",
            json={"policy_id": "pol-a", "name": "A", "scope": "agent", "action": "deny"},
        )
        client.post(
            "/api/v1/org-policies",
            json={"policy_id": "pol-s", "name": "S", "scope": "sandbox", "action": "deny"},
        )
        resp = client.get("/api/v1/org-policies", params={"scope": "sandbox"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["scope"] == "sandbox"

    def test_get_existing_returns_200(self, client: TestClient) -> None:
        client.post(
            "/api/v1/org-policies",
            json={"policy_id": "pol-3", "name": "P3", "scope": "agent", "action": "deny"},
        )
        resp = client.get("/api/v1/org-policies/pol-3")
        assert resp.status_code == 200
        assert resp.json()["policy_id"] == "pol-3"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/org-policies/nonexistent")
        assert resp.status_code == 404

    def test_evaluate_no_policies_returns_allowed(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/org-policies/evaluate",
            json={"agent_id": "a1", "action_type": "agent", "resource": "res1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["violations"] == []

    def test_evaluate_matching_deny_returns_not_allowed(self, client: TestClient) -> None:
        client.post(
            "/api/v1/org-policies",
            json={"policy_id": "pol-deny", "name": "Block", "scope": "agent", "action": "deny"},
        )
        resp = client.post(
            "/api/v1/org-policies/evaluate",
            json={"agent_id": "a1", "action_type": "agent", "resource": "res1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert len(data["violations"]) == 1
        assert data["violations"][0]["policy_id"] == "pol-deny"
