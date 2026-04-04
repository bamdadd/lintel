"""Tests for encryption API routes."""

from fastapi.testclient import TestClient


class TestEncryptionStatus:
    def test_status_returns_active_key(self, client: TestClient) -> None:
        resp = client.get("/api/v1/encryption/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_key_id"]
        assert data["total_keys"] == 1
        assert len(data["keys"]) == 1
        assert data["keys"][0]["active"] is True


class TestKeyRotation:
    def test_rotate_returns_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/encryption/keys")
        assert resp.status_code == 201
        data = resp.json()
        assert data["active"] is True
        assert data["key_id"]

    def test_rotate_increments_key_count(self, client: TestClient) -> None:
        client.post("/api/v1/encryption/keys")
        resp = client.get("/api/v1/encryption/status")
        data = resp.json()
        assert data["total_keys"] == 2
        active_keys = [k for k in data["keys"] if k["active"]]
        assert len(active_keys) == 1
