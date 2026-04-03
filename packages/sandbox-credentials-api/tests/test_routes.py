"""Tests for the sandbox credentials API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestIssueCredential:
    def test_issue_credential(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "cred-1",
                "sandbox_id": "sbx-1",
                "credential_type": "api_key",
                "name": "Test Key",
                "scopes": ["read", "write"],
                "ttl_seconds": 1800,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "cred-1"
        assert data["sandbox_id"] == "sbx-1"
        assert data["credential_type"] == "api_key"
        assert data["name"] == "Test Key"
        assert data["scopes"] == ["read", "write"]
        assert data["status"] == "active"
        assert "issued_at" in data
        assert "expires_at" in data

    def test_issue_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "id": "cred-1",
            "sandbox_id": "sbx-1",
            "credential_type": "api_key",
            "name": "Key",
        }
        client.post("/api/v1/sandbox-credentials", json=body)
        resp = client.post("/api/v1/sandbox-credentials", json=body)
        assert resp.status_code == 409


class TestListCredentials:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-credentials")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_all(self, client: TestClient) -> None:
        for i in range(3):
            client.post(
                "/api/v1/sandbox-credentials",
                json={
                    "id": f"cred-{i}",
                    "sandbox_id": "sbx-1",
                    "credential_type": "api_key",
                    "name": f"Key {i}",
                },
            )
        resp = client.get("/api/v1/sandbox-credentials")
        assert len(resp.json()) == 3

    def test_filter_by_sandbox_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "c1",
                "sandbox_id": "sbx-1",
                "credential_type": "api_key",
                "name": "A",
            },
        )
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "c2",
                "sandbox_id": "sbx-2",
                "credential_type": "api_key",
                "name": "B",
            },
        )
        resp = client.get("/api/v1/sandbox-credentials?sandbox_id=sbx-1")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sandbox_id"] == "sbx-1"


class TestGetCredential:
    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "cred-1",
                "sandbox_id": "sbx-1",
                "credential_type": "github_token",
                "name": "GH Token",
            },
        )
        resp = client.get("/api/v1/sandbox-credentials/cred-1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GH Token"

    def test_get_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandbox-credentials/nope")
        assert resp.status_code == 404


class TestUpdateCredential:
    def test_update_name(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "cred-1",
                "sandbox_id": "sbx-1",
                "credential_type": "api_key",
                "name": "Old Name",
            },
        )
        resp = client.patch(
            "/api/v1/sandbox-credentials/cred-1",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/sandbox-credentials/nope",
            json={"name": "X"},
        )
        assert resp.status_code == 404


class TestRevokeCredential:
    def test_revoke_active(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "cred-1",
                "sandbox_id": "sbx-1",
                "credential_type": "api_key",
                "name": "Key",
            },
        )
        resp = client.post("/api/v1/sandbox-credentials/cred-1/revoke")
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"
        assert resp.json()["revoked_at"] is not None

    def test_revoke_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sandbox-credentials/nope/revoke")
        assert resp.status_code == 404

    def test_revoke_already_revoked(self, client: TestClient) -> None:
        client.post(
            "/api/v1/sandbox-credentials",
            json={
                "id": "cred-1",
                "sandbox_id": "sbx-1",
                "credential_type": "api_key",
                "name": "Key",
            },
        )
        client.post("/api/v1/sandbox-credentials/cred-1/revoke")
        resp = client.post("/api/v1/sandbox-credentials/cred-1/revoke")
        assert resp.status_code == 409


class TestRevokeAllForSandbox:
    def test_revoke_all(self, client: TestClient) -> None:
        for i in range(3):
            client.post(
                "/api/v1/sandbox-credentials",
                json={
                    "id": f"cred-{i}",
                    "sandbox_id": "sbx-1",
                    "credential_type": "api_key",
                    "name": f"Key {i}",
                },
            )
        resp = client.post(
            "/api/v1/sandbox-credentials/sandbox/sbx-1/revoke-all",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_id"] == "sbx-1"
        assert data["revoked_count"] == 3

    def test_revoke_all_empty(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandbox-credentials/sandbox/sbx-99/revoke-all",
        )
        assert resp.status_code == 200
        assert resp.json()["revoked_count"] == 0
