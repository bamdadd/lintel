"""Tests for digest API routes."""

from fastapi.testclient import TestClient


class TestDigestAPI:
    def test_create_digest_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digests",
            json={
                "id": "d-1",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Good week",
                "highlights": ["Shipped feature X"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "d-1"
        assert data["summary"] == "Good week"
        assert data["highlights"] == ["Shipped feature X"]

    def test_list_digests_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digests")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_digest_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digests",
            json={
                "id": "d-2",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Summary",
            },
        )
        resp = client.get("/api/v1/digests/d-2")
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Summary"

    def test_get_digest_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digests/nonexistent")
        assert resp.status_code == 404

    def test_delete_digest_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digests",
            json={
                "id": "d-3",
                "project_id": "p-1",
                "team_id": "t-1",
                "period_start": "2026-03-24T00:00:00Z",
                "period_end": "2026-03-31T00:00:00Z",
                "summary": "Bye",
            },
        )
        resp = client.delete("/api/v1/digests/d-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/digests/d-3").status_code == 404


class TestDigestConfigAPI:
    def test_create_config_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/digest-configs",
            json={
                "id": "dc-1",
                "project_id": "p-1",
                "schedule": "weekly",
                "recipients": ["alice@example.com"],
                "enabled": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "dc-1"
        assert data["schedule"] == "weekly"
        assert data["recipients"] == ["alice@example.com"]

    def test_list_configs_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digest-configs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_config_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-2", "project_id": "p-1"},
        )
        resp = client.get("/api/v1/digest-configs/dc-2")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "p-1"

    def test_get_config_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/digest-configs/nonexistent")
        assert resp.status_code == 404

    def test_update_config(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-3", "project_id": "p-1", "schedule": "weekly"},
        )
        resp = client.patch(
            "/api/v1/digest-configs/dc-3",
            json={"schedule": "daily"},
        )
        assert resp.status_code == 200
        assert resp.json()["schedule"] == "daily"

    def test_update_config_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/digest-configs/nonexistent",
            json={"schedule": "daily"},
        )
        assert resp.status_code == 404

    def test_delete_config_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-4", "project_id": "p-1"},
        )
        resp = client.delete("/api/v1/digest-configs/dc-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/digest-configs/dc-4").status_code == 404

    def test_update_config_recipients(self, client: TestClient) -> None:
        client.post(
            "/api/v1/digest-configs",
            json={"id": "dc-5", "project_id": "p-1", "recipients": ["a@b.com"]},
        )
        resp = client.patch(
            "/api/v1/digest-configs/dc-5",
            json={"recipients": ["x@y.com", "z@w.com"]},
        )
        assert resp.status_code == 200
        assert resp.json()["recipients"] == ["x@y.com", "z@w.com"]
