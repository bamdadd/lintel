"""Tests for multiplayer sessions API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_create_session(client: TestClient) -> None:
    resp = client.post("/api/v1/sessions", json={"name": "Pair session", "created_by": "u1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Pair session"
    assert data["created_by"] == "u1"
    assert data["status"] == "active"
    assert len(data["participants"]) == 1
    assert data["participants"][0]["user_id"] == "u1"
    assert data["participants"][0]["role"] == "owner"


def test_list_sessions_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_sessions(client: TestClient) -> None:
    client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    client.post("/api/v1/sessions", json={"name": "S2", "created_by": "u2"})
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_session(client: TestClient) -> None:
    create_resp = client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    sid = create_resp.json()["session_id"]
    resp = client.get(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid


def test_get_session_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/sessions/nonexistent")
    assert resp.status_code == 404


def test_join_session(client: TestClient) -> None:
    create_resp = client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    sid = create_resp.json()["session_id"]
    resp = client.post(f"/api/v1/sessions/{sid}/join", json={"user_id": "u2"})
    assert resp.status_code == 200
    assert len(resp.json()["participants"]) == 2


def test_join_session_duplicate(client: TestClient) -> None:
    create_resp = client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    sid = create_resp.json()["session_id"]
    resp = client.post(f"/api/v1/sessions/{sid}/join", json={"user_id": "u1"})
    assert resp.status_code == 409


def test_join_session_not_found(client: TestClient) -> None:
    resp = client.post("/api/v1/sessions/nonexistent/join", json={"user_id": "u1"})
    assert resp.status_code == 404


def test_leave_session(client: TestClient) -> None:
    create_resp = client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    sid = create_resp.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/join", json={"user_id": "u2"})
    resp = client.post(f"/api/v1/sessions/{sid}/leave", json={"user_id": "u2"})
    assert resp.status_code == 200
    assert len(resp.json()["participants"]) == 1


def test_leave_session_not_participant(client: TestClient) -> None:
    create_resp = client.post("/api/v1/sessions", json={"name": "S1", "created_by": "u1"})
    sid = create_resp.json()["session_id"]
    resp = client.post(f"/api/v1/sessions/{sid}/leave", json={"user_id": "u99"})
    assert resp.status_code == 404


def test_leave_session_not_found(client: TestClient) -> None:
    resp = client.post("/api/v1/sessions/nonexistent/leave", json={"user_id": "u1"})
    assert resp.status_code == 404
