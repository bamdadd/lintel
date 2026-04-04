"""Tests for the secret rotation API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestRotationPolicies:
    def test_create_rotation_policy(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-1",
                "credential_id": "cred-1",
                "rotation_interval_days": 30,
                "alert_before_days": 7,
                "auto_rotate": False,
                "description": "Monthly rotation",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "pol-1"
        assert data["credential_id"] == "cred-1"
        assert data["rotation_interval_days"] == 30
        assert "next_rotation_at" in data

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "policy_id": "pol-1",
            "credential_id": "cred-1",
            "rotation_interval_days": 30,
        }
        client.post("/api/v1/secrets/rotation-policies", json=body)
        resp = client.post("/api/v1/secrets/rotation-policies", json=body)
        assert resp.status_code == 409

    def test_list_policies_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/secrets/rotation-policies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_policies(self, client: TestClient) -> None:
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={"credential_id": "c1", "rotation_interval_days": 30},
        )
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={"credential_id": "c2", "rotation_interval_days": 60},
        )
        resp = client.get("/api/v1/secrets/rotation-policies")
        assert len(resp.json()) == 2

    def test_get_policy(self, client: TestClient) -> None:
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-1",
                "credential_id": "cred-1",
                "rotation_interval_days": 30,
            },
        )
        resp = client.get("/api/v1/secrets/rotation-policies/pol-1")
        assert resp.status_code == 200
        assert resp.json()["policy_id"] == "pol-1"

    def test_get_policy_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/secrets/rotation-policies/nope")
        assert resp.status_code == 404

    def test_delete_policy(self, client: TestClient) -> None:
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-1",
                "credential_id": "cred-1",
                "rotation_interval_days": 30,
            },
        )
        resp = client.delete("/api/v1/secrets/rotation-policies/pol-1")
        assert resp.status_code == 204
        assert client.get("/api/v1/secrets/rotation-policies/pol-1").status_code == 404

    def test_delete_policy_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/secrets/rotation-policies/nope")
        assert resp.status_code == 404


class TestRotateCredential:
    def test_rotate_with_policy(self, client: TestClient) -> None:
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-1",
                "credential_id": "cred-1",
                "rotation_interval_days": 30,
            },
        )
        resp = client.post(
            "/api/v1/secrets/rotate/cred-1",
            json={"rotated_by": "admin"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["credential_id"] == "cred-1"
        assert data["rotated_by"] == "admin"
        assert "new_expires_at" in data

    def test_rotate_without_policy(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/secrets/rotate/cred-orphan",
            json={"rotated_by": "admin"},
        )
        assert resp.status_code == 201
        assert resp.json()["credential_id"] == "cred-orphan"

    def test_rotate_with_explicit_expiry(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/secrets/rotate/cred-1",
            json={"rotated_by": "admin", "new_expires_at": "2099-12-31T00:00:00+00:00"},
        )
        assert resp.status_code == 201
        assert resp.json()["new_expires_at"] == "2099-12-31T00:00:00+00:00"


class TestRotationHistory:
    def test_get_history(self, client: TestClient) -> None:
        client.post(
            "/api/v1/secrets/rotate/cred-1",
            json={"rotated_by": "admin"},
        )
        client.post(
            "/api/v1/secrets/rotate/cred-1",
            json={"rotated_by": "bot"},
        )
        resp = client.get("/api/v1/secrets/rotation-history/cred-1")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_history_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/secrets/rotation-history/no-cred")
        assert resp.status_code == 200
        assert resp.json() == []


class TestExpiringCredentials:
    def test_list_expiring(self, client: TestClient) -> None:
        # Create a policy with 1-day rotation (will expire very soon)
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-short",
                "credential_id": "cred-short",
                "rotation_interval_days": 1,
            },
        )
        resp = client.get("/api/v1/secrets/expiring?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["credential_id"] == "cred-short"

    def test_list_expiring_none(self, client: TestClient) -> None:
        # Create a policy with 365-day rotation
        client.post(
            "/api/v1/secrets/rotation-policies",
            json={
                "policy_id": "pol-long",
                "credential_id": "cred-long",
                "rotation_interval_days": 365,
            },
        )
        # Only check within 1 day — should not find the 365-day one
        resp = client.get("/api/v1/secrets/expiring?days=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_list_expiring_default_days(self, client: TestClient) -> None:
        resp = client.get("/api/v1/secrets/expiring")
        assert resp.status_code == 200
        assert resp.json() == []
