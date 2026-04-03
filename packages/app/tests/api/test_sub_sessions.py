"""Tests for sub-session API routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.agents.sub_sessions import SubSessionManager
from lintel.api.routes.sub_sessions import _sub_session_manager_provider, router


def _make_client() -> tuple[TestClient, SubSessionManager]:
    mgr = SubSessionManager()
    _sub_session_manager_provider.override(mgr)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app), mgr


class TestSubSessionRoutes:
    def test_list_empty(self) -> None:
        client, _ = _make_client()
        resp = client.get("/api/v1/sub-sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_sessions(self) -> None:
        client, mgr = _make_client()
        mgr.spawn("parent-1", "org/a", "prompt a")
        mgr.spawn("parent-2", "org/b", "prompt b")
        resp = client.get("/api/v1/sub-sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_filtered_by_parent(self) -> None:
        client, mgr = _make_client()
        mgr.spawn("parent-1", "org/a", "prompt a")
        mgr.spawn("parent-1", "org/b", "prompt b")
        mgr.spawn("parent-2", "org/c", "prompt c")
        resp = client.get("/api/v1/sub-sessions", params={"parent_session_id": "parent-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(s["parent_session_id"] == "parent-1" for s in data)

    def test_get_session(self) -> None:
        client, mgr = _make_client()
        session = mgr.spawn("parent-1", "org/repo", "investigate auth")
        resp = client.get(f"/api/v1/sub-sessions/{session.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo"] == "org/repo"
        assert data["status"] == "pending"

    def test_get_completed_session(self) -> None:
        client, mgr = _make_client()
        session = mgr.spawn("parent-1", "org/repo", "find patterns")
        mgr.mark_running(session.session_id)
        mgr.mark_completed(session.session_id, "Found OAuth2 flow")
        resp = client.get(f"/api/v1/sub-sessions/{session.session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "Found OAuth2 flow"

    def test_get_not_found(self) -> None:
        client, _ = _make_client()
        resp = client.get("/api/v1/sub-sessions/nonexistent")
        assert resp.status_code == 404
