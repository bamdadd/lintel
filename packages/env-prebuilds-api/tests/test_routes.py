"""Tests for environment prebuilds API."""

from fastapi.testclient import TestClient


def _create_config(
    client: TestClient,
    config_id: str = "cfg1",
) -> dict:  # type: ignore[type-arg]
    return client.post(
        "/api/v1/prebuilds/configs",
        json={
            "config_id": config_id,
            "name": "Warm Python Env",
            "environment_id": "env-python",
            "image": "python:3.12",
            "setup_commands": ["pip install numpy"],
            "warmup_count": 2,
        },
    ).json()


class TestPrebuildConfigs:
    def test_create_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/prebuilds/configs",
            json={
                "config_id": "cfg1",
                "name": "Node Env",
                "environment_id": "env-node",
                "image": "node:20",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["config_id"] == "cfg1"
        assert data["name"] == "Node Env"
        assert data["environment_id"] == "env-node"
        assert data["warmup_count"] == 1

    def test_create_config_duplicate_returns_409(self, client: TestClient) -> None:
        _create_config(client, "dup")
        resp = client.post(
            "/api/v1/prebuilds/configs",
            json={"config_id": "dup", "name": "Again", "environment_id": "env1"},
        )
        assert resp.status_code == 409

    def test_list_configs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/prebuilds/configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_configs_with_items(self, client: TestClient) -> None:
        _create_config(client, "a")
        _create_config(client, "b")
        resp = client.get("/api/v1/prebuilds/configs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_config_by_id(self, client: TestClient) -> None:
        _create_config(client, "cfg1")
        resp = client.get("/api/v1/prebuilds/configs/cfg1")
        assert resp.status_code == 200
        assert resp.json()["config_id"] == "cfg1"

    def test_get_config_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/prebuilds/configs/missing")
        assert resp.status_code == 404


class TestPrebuildTrigger:
    def test_trigger_prebuild(self, client: TestClient) -> None:
        _create_config(client, "cfg1")
        resp = client.post(
            "/api/v1/prebuilds/trigger",
            json={"config_id": "cfg1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["config_id"] == "cfg1"
        assert data["status"] == "pending"
        assert "run_id" in data

    def test_trigger_prebuild_missing_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/prebuilds/trigger",
            json={"config_id": "nonexistent"},
        )
        assert resp.status_code == 404


class TestPrebuildStatus:
    def test_list_status_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/prebuilds/status")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_status_after_trigger(self, client: TestClient) -> None:
        _create_config(client, "cfg1")
        client.post("/api/v1/prebuilds/trigger", json={"config_id": "cfg1"})
        client.post("/api/v1/prebuilds/trigger", json={"config_id": "cfg1"})
        resp = client.get("/api/v1/prebuilds/status")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_status_filtered_by_config(self, client: TestClient) -> None:
        _create_config(client, "a")
        _create_config(client, "b")
        client.post("/api/v1/prebuilds/trigger", json={"config_id": "a"})
        client.post("/api/v1/prebuilds/trigger", json={"config_id": "b"})
        resp = client.get("/api/v1/prebuilds/status", params={"config_id": "a"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["config_id"] == "a"
