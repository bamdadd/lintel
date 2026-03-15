"""Tests for variables API."""

from fastapi.testclient import TestClient


class TestVariablesAPI:
    def test_create_variable_returns_201(
        self,
        client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/variables",
            json={
                "variable_id": "v-1",
                "key": "DATABASE_URL",
                "value": "postgres://localhost/db",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["variable_id"] == "v-1"
        assert data["key"] == "DATABASE_URL"

    def test_list_variables_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/variables")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_variable_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/variables",
            json={
                "variable_id": "v-2",
                "key": "API_KEY",
                "value": "secret123",
            },
        )
        resp = client.get("/api/v1/variables/v-2")
        assert resp.status_code == 200
        assert resp.json()["key"] == "API_KEY"

    def test_get_variable_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/variables/nonexistent")
        assert resp.status_code == 404

    def test_delete_variable_returns_204(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/variables",
            json={
                "variable_id": "v-3",
                "key": "TMP",
                "value": "val",
            },
        )
        resp = client.delete("/api/v1/variables/v-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/variables/v-3").status_code == 404

    def test_secret_variable_value_is_masked(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/variables",
            json={
                "variable_id": "v-secret",
                "key": "TOKEN",
                "value": "supersecretvalue",
                "is_secret": True,
            },
        )
        resp = client.get("/api/v1/variables/v-secret")
        assert resp.status_code == 200
        assert resp.json()["value"] == "supe****"
