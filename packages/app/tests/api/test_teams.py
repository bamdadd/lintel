"""Tests for teams API."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


class TestTeamsAPI:
    def test_create_team_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/teams",
            json={
                "team_id": "team-1",
                "name": "Backend",
                "member_ids": ["u-1", "u-2"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["team_id"] == "team-1"
        assert data["name"] == "Backend"
        assert data["member_ids"] == ["u-1", "u-2"]

    def test_list_teams_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/teams")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_team_by_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/teams",
            json={
                "team_id": "team-2",
                "name": "Frontend",
            },
        )
        resp = client.get("/api/v1/teams/team-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Frontend"

    def test_get_team_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/teams/nonexistent")
        assert resp.status_code == 404

    def test_delete_team_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/teams",
            json={
                "team_id": "team-3",
                "name": "To Delete",
            },
        )
        resp = client.delete("/api/v1/teams/team-3")
        assert resp.status_code == 204
        assert client.get("/api/v1/teams/team-3").status_code == 404
