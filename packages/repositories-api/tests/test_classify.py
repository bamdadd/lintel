"""Tests for the repository auto-classification endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _register_repo(
    client: TestClient,
    repo_id: str,
    name: str,
    url: str = "https://github.com/acme/repo",
    owner: str = "acme",
) -> None:
    client.post(
        "/api/v1/repositories",
        json={
            "repo_id": repo_id,
            "name": name,
            "url": url,
            "owner": owner,
        },
    )


class TestClassifyRepository:
    def test_classify_matches_repo(self, client: TestClient) -> None:
        _register_repo(client, "r1", "lintel", "https://github.com/acme/lintel")
        _register_repo(client, "r2", "other-app", "https://github.com/acme/other-app")
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "fix the lintel CI pipeline"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["results"][0]["repo_id"] == "r1"
        assert data["results"][0]["confidence"] > 0
        assert data["needs_clarification"] is False

    def test_classify_no_match(self, client: TestClient) -> None:
        _register_repo(client, "r1", "backend", "https://github.com/acme/backend")
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "hello world nothing related"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["needs_clarification"] is True

    def test_classify_low_confidence_needs_clarification(
        self,
        client: TestClient,
    ) -> None:
        _register_repo(
            client,
            "r1",
            "data-pipeline",
            "https://github.com/acme/data-pipeline",
        )
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "the data is wrong"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Partial match on "data" — low confidence
        if data["results"]:
            assert data["results"][0]["confidence"] < 0.5

    def test_classify_empty_repos(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "fix something"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["needs_clarification"] is True

    def test_classify_top_k(self, client: TestClient) -> None:
        for i in range(5):
            _register_repo(
                client,
                f"r{i}",
                f"app-{i}",
                f"https://github.com/acme/app-{i}",
            )
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "update app-0 app-1 app-2 app-3 app-4", "top_k": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_classify_returns_keywords_and_reason(self, client: TestClient) -> None:
        _register_repo(client, "r1", "lintel", "https://github.com/acme/lintel")
        resp = client.post(
            "/api/v1/repositories/classify",
            json={"message": "fix lintel bug"},
        )
        data = resp.json()
        result = data["results"][0]
        assert len(result["matched_keywords"]) > 0
        assert result["reason"] != ""
