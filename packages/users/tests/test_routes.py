"""Tests for users API."""

from fastapi.testclient import TestClient


class TestUsersAPI:
    def test_create_user_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/users",
            json={
                "user_id": "u-1",
                "name": "Alice",
                "email": "alice@example.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "u-1"
        assert data["name"] == "Alice"
        assert data["role"] == "member"

    def test_list_users_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_user_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={
                "user_id": "u-2",
                "name": "Bob",
            },
        )
        resp = client.get("/api/v1/users/u-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"

    def test_get_user_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_delete_user_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={
                "user_id": "u-3",
                "name": "Charlie",
            },
        )
        resp = client.delete("/api/v1/users/u-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/users/u-3").status_code == 404


class TestSlackUserMapping:
    def test_create_user_with_slack_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/users",
            json={
                "user_id": "u-s1",
                "name": "Alice",
                "slack_user_id": "U12345",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["slack_user_id"] == "U12345"

    def test_get_user_by_slack_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={"user_id": "u-s2", "name": "Bob", "slack_user_id": "U67890"},
        )
        resp = client.get("/api/v1/users/by-slack-id/U67890")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "u-s2"

    def test_get_user_by_slack_id_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/by-slack-id/U99999")
        assert resp.status_code == 404

    def test_link_slack_to_user(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={"user_id": "u-s3", "name": "Charlie"},
        )
        resp = client.post(
            "/api/v1/users/u-s3/link-slack",
            json={"slack_user_id": "UABC"},
        )
        assert resp.status_code == 200
        assert resp.json()["slack_user_id"] == "UABC"
        # Verify lookup works
        lookup = client.get("/api/v1/users/by-slack-id/UABC")
        assert lookup.status_code == 200
        assert lookup.json()["user_id"] == "u-s3"

    def test_link_slack_conflict(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={"user_id": "u-s4", "name": "Dave", "slack_user_id": "UXYZ"},
        )
        client.post(
            "/api/v1/users",
            json={"user_id": "u-s5", "name": "Eve"},
        )
        resp = client.post(
            "/api/v1/users/u-s5/link-slack",
            json={"slack_user_id": "UXYZ"},
        )
        assert resp.status_code == 409

    def test_link_slack_user_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/users/nonexistent/link-slack",
            json={"slack_user_id": "UFOO"},
        )
        assert resp.status_code == 404

    def test_update_user_slack_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/users",
            json={"user_id": "u-s6", "name": "Frank"},
        )
        resp = client.patch(
            "/api/v1/users/u-s6",
            json={"slack_user_id": "UNEW"},
        )
        assert resp.status_code == 200
        assert resp.json()["slack_user_id"] == "UNEW"
