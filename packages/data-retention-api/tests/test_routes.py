"""Tests for data retention API."""

from fastapi.testclient import TestClient


class TestRetentionPoliciesAPI:
    def test_create_policy_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/retention/policies",
            json={
                "policy_id": "rp-1",
                "entity_type": "audit_entry",
                "max_age_days": 90,
                "action": "delete",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "rp-1"
        assert data["entity_type"] == "audit_entry"
        assert data["max_age_days"] == 90
        assert data["action"] == "delete"

    def test_create_policy_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "policy_id": "rp-dup",
            "entity_type": "event",
            "max_age_days": 30,
            "action": "archive",
        }
        client.post("/api/v1/retention/policies", json=body)
        resp = client.post("/api/v1/retention/policies", json=body)
        assert resp.status_code == 409

    def test_list_policies_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/retention/policies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_policies_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/retention/policies",
            json={
                "policy_id": "rp-list",
                "entity_type": "pipeline",
                "max_age_days": 60,
                "action": "archive",
            },
        )
        resp = client.get("/api/v1/retention/policies")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_policy_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/retention/policies",
            json={
                "policy_id": "rp-get",
                "entity_type": "chat",
                "max_age_days": 365,
                "action": "delete",
            },
        )
        resp = client.get("/api/v1/retention/policies/rp-get")
        assert resp.status_code == 200
        assert resp.json()["entity_type"] == "chat"

    def test_get_policy_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/retention/policies/nonexistent")
        assert resp.status_code == 404

    def test_delete_policy_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/retention/policies",
            json={
                "policy_id": "rp-del",
                "entity_type": "log",
                "max_age_days": 7,
                "action": "delete",
            },
        )
        resp = client.delete("/api/v1/retention/policies/rp-del")
        assert resp.status_code == 204
        assert client.get("/api/v1/retention/policies/rp-del").status_code == 404

    def test_delete_policy_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/retention/policies/nonexistent")
        assert resp.status_code == 404

    def test_run_retention_returns_results(self, client: TestClient) -> None:
        client.post(
            "/api/v1/retention/policies",
            json={
                "policy_id": "rp-run",
                "entity_type": "audit_entry",
                "max_age_days": 30,
                "action": "delete",
            },
        )
        resp = client.post("/api/v1/retention/run", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["policies_evaluated"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["policy_id"] == "rp-run"

    def test_run_retention_no_policies(self, client: TestClient) -> None:
        resp = client.post("/api/v1/retention/run", json={})
        assert resp.status_code == 200
        assert resp.json()["policies_evaluated"] == 0

    def test_create_policy_invalid_action_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/retention/policies",
            json={
                "entity_type": "event",
                "max_age_days": 30,
                "action": "invalid",
            },
        )
        assert resp.status_code == 422

    def test_create_policy_invalid_max_age_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/retention/policies",
            json={
                "entity_type": "event",
                "max_age_days": 0,
                "action": "delete",
            },
        )
        assert resp.status_code == 422
