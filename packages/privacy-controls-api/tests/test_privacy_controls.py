"""Tests for privacy controls API endpoints (REQ-008)."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_visibility(
    client: TestClient,
    user_id: str = "user-1",
    metric_type: str = "velocity",
    privacy_level: str = "private",
    allowed_viewers: list[str] | None = None,
) -> dict:
    resp = client.post(
        "/api/v1/privacy/visibility",
        json={
            "user_id": user_id,
            "metric_type": metric_type,
            "privacy_level": privacy_level,
            "allowed_viewers": allowed_viewers or [],
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestVisibilityAPI:
    def test_create_visibility(self, client: TestClient) -> None:
        data = _create_visibility(client)
        assert data["user_id"] == "user-1"
        assert data["metric_type"] == "velocity"
        assert data["privacy_level"] == "private"
        assert data["allowed_viewers"] == []

    def test_create_visibility_with_viewers(self, client: TestClient) -> None:
        data = _create_visibility(
            client,
            allowed_viewers=["viewer-a", "viewer-b"],
        )
        assert data["allowed_viewers"] == ["viewer-a", "viewer-b"]

    def test_list_visibility(self, client: TestClient) -> None:
        _create_visibility(client, user_id="u1", metric_type="m1")
        _create_visibility(client, user_id="u2", metric_type="m2")
        resp = client.get("/api/v1/privacy/visibility")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_visibility(self, client: TestClient) -> None:
        created = _create_visibility(client)
        vid = created["visibility_id"]
        resp = client.get(f"/api/v1/privacy/visibility/{vid}")
        assert resp.status_code == 200
        assert resp.json()["visibility_id"] == vid

    def test_get_visibility_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/privacy/visibility/missing").status_code == 404

    def test_update_visibility(self, client: TestClient) -> None:
        created = _create_visibility(client)
        vid = created["visibility_id"]
        resp = client.patch(
            f"/api/v1/privacy/visibility/{vid}",
            json={"privacy_level": "team_only"},
        )
        assert resp.status_code == 200
        assert resp.json()["privacy_level"] == "team_only"

    def test_update_visibility_allowed_viewers(self, client: TestClient) -> None:
        created = _create_visibility(client)
        vid = created["visibility_id"]
        resp = client.patch(
            f"/api/v1/privacy/visibility/{vid}",
            json={"allowed_viewers": ["viewer-x"]},
        )
        assert resp.status_code == 200
        assert resp.json()["allowed_viewers"] == ["viewer-x"]

    def test_update_visibility_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/privacy/visibility/missing",
            json={"privacy_level": "public"},
        )
        assert resp.status_code == 404

    def test_delete_visibility(self, client: TestClient) -> None:
        created = _create_visibility(client)
        vid = created["visibility_id"]
        assert client.delete(f"/api/v1/privacy/visibility/{vid}").status_code == 204
        assert client.get(f"/api/v1/privacy/visibility/{vid}").status_code == 404

    def test_delete_visibility_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/privacy/visibility/missing").status_code == 404

    def test_privacy_levels(self, client: TestClient) -> None:
        for level in ("public", "team_only", "private"):
            data = _create_visibility(
                client,
                user_id=f"u-{level}",
                metric_type=f"m-{level}",
                privacy_level=level,
            )
            assert data["privacy_level"] == level


class TestPreferenceAPI:
    def test_put_preference(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/privacy/preferences/user-1",
            json={"default_privacy_level": "team_only", "opt_out_metrics": ["velocity"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user-1"
        assert data["default_privacy_level"] == "team_only"
        assert data["opt_out_metrics"] == ["velocity"]

    def test_get_preference(self, client: TestClient) -> None:
        client.put(
            "/api/v1/privacy/preferences/user-2",
            json={"default_privacy_level": "private"},
        )
        resp = client.get("/api/v1/privacy/preferences/user-2")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-2"

    def test_get_preference_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/privacy/preferences/missing").status_code == 404

    def test_put_preference_overwrite(self, client: TestClient) -> None:
        client.put(
            "/api/v1/privacy/preferences/user-3",
            json={"default_privacy_level": "public"},
        )
        resp = client.put(
            "/api/v1/privacy/preferences/user-3",
            json={"default_privacy_level": "private", "opt_out_metrics": ["throughput"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_privacy_level"] == "private"
        assert data["opt_out_metrics"] == ["throughput"]
