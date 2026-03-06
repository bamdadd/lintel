"""Tests for the credentials API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestCredentialsAPI:
    def test_store_ssh_key(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "key-1",
                "credential_type": "ssh_key",
                "name": "Deploy key",
                "secret": "ssh-rsa AAAAB3...longkey",
                "repo_ids": ["repo-1"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["credential_id"] == "key-1"
        assert data["credential_type"] == "ssh_key"
        assert data["name"] == "Deploy key"
        assert "secret_preview" in data
        assert "AAAA" not in data.get("secret", "")
        assert data["repo_ids"] == ["repo-1"]

    def test_store_github_token(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "ghtoken-1",
                "credential_type": "github_token",
                "name": "CI Token",
                "secret": "ghp_1234567890abcdef",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["credential_type"] == "github_token"
        assert "secret_preview" in data

    def test_store_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "credential_id": "key-1",
            "credential_type": "ssh_key",
            "name": "Key",
            "secret": "ssh-rsa AAAA",
        }
        client.post("/api/v1/credentials", json=body)
        resp = client.post("/api/v1/credentials", json=body)
        assert resp.status_code == 409

    def test_list_credentials_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/credentials")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_credentials(self, client: TestClient) -> None:
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k1",
                "credential_type": "ssh_key",
                "name": "A",
                "secret": "secret-a",
            },
        )
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k2",
                "credential_type": "github_token",
                "name": "B",
                "secret": "secret-b",
            },
        )
        resp = client.get("/api/v1/credentials")
        assert len(resp.json()) == 2

    def test_get_credential(self, client: TestClient) -> None:
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k1",
                "credential_type": "ssh_key",
                "name": "Key",
                "secret": "ssh-rsa AAAA",
            },
        )
        resp = client.get("/api/v1/credentials/k1")
        assert resp.status_code == 200
        assert resp.json()["credential_id"] == "k1"

    def test_get_credential_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/credentials/nope")
        assert resp.status_code == 404

    def test_list_by_repo(self, client: TestClient) -> None:
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k1",
                "credential_type": "ssh_key",
                "name": "For repo-1",
                "secret": "secret",
                "repo_ids": ["repo-1"],
            },
        )
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k2",
                "credential_type": "github_token",
                "name": "Global",
                "secret": "secret",
                "repo_ids": [],
            },
        )
        resp = client.get("/api/v1/credentials/repo/repo-1")
        assert resp.status_code == 200
        ids = [c["credential_id"] for c in resp.json()]
        assert "k1" in ids
        assert "k2" in ids  # global cred applies to all repos

    def test_revoke_credential(self, client: TestClient) -> None:
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k1",
                "credential_type": "ssh_key",
                "name": "Key",
                "secret": "secret",
            },
        )
        resp = client.delete("/api/v1/credentials/k1")
        assert resp.status_code == 204
        assert client.get("/api/v1/credentials/k1").status_code == 404

    def test_revoke_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/credentials/nope")
        assert resp.status_code == 404

    def test_secret_not_exposed_in_list(self, client: TestClient) -> None:
        client.post(
            "/api/v1/credentials",
            json={
                "credential_id": "k1",
                "credential_type": "github_token",
                "name": "Token",
                "secret": "ghp_supersecretvalue123",
            },
        )
        resp = client.get("/api/v1/credentials")
        for cred in resp.json():
            assert "secret" not in cred or cred.get("secret") != "ghp_supersecretvalue123"
