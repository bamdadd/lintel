"""Tests for playbooks API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestPlaybooksAPI:
    def test_create_playbook_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/playbooks",
            json={
                "playbook_id": "pb-1",
                "title": "Parallel Agent Strategy",
                "strategy": "Use parallel execution for independent tasks",
                "source_synthesis_ids": ["syn-1"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["playbook_id"] == "pb-1"
        assert data["title"] == "Parallel Agent Strategy"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = {"playbook_id": "pb-dup", "title": "test"}
        client.post("/api/v1/playbooks", json=payload)
        resp = client.post("/api/v1/playbooks", json=payload)
        assert resp.status_code == 409

    def test_get_playbook(self, client: TestClient) -> None:
        client.post(
            "/api/v1/playbooks",
            json={"playbook_id": "pb-get", "title": "test"},
        )
        resp = client.get("/api/v1/playbooks/pb-get")
        assert resp.status_code == 200
        assert resp.json()["playbook_id"] == "pb-get"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/playbooks/missing")
        assert resp.status_code == 404

    def test_list_playbooks(self, client: TestClient) -> None:
        client.post("/api/v1/playbooks", json={"playbook_id": "pb-l1", "title": "a"})
        client.post("/api/v1/playbooks", json={"playbook_id": "pb-l2", "title": "b"})
        resp = client.get("/api/v1/playbooks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
