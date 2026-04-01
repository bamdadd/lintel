"""Tests for review-scores-api routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_create_review_score(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/review-scores",
        json={
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.5,
            "severity": "medium",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["repo_id"] == "repo-1"
    assert data["dimension"] == "security"
    assert data["score"] == 7.5
    assert "recorded_at" in data


def test_get_repo_score_trends(client: TestClient) -> None:
    client.post(
        "/api/v1/review-scores",
        json={
            "score_id": "s1",
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.0,
        },
    )
    client.post(
        "/api/v1/review-scores",
        json={
            "score_id": "s2",
            "repo_id": "repo-1",
            "dimension": "correctness",
            "score": 8.0,
        },
    )

    resp = client.get("/api/v1/repositories/repo-1/review-scores/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_repo_score_trends_filtered(client: TestClient) -> None:
    client.post(
        "/api/v1/review-scores",
        json={
            "score_id": "s1",
            "repo_id": "repo-1",
            "dimension": "security",
            "score": 7.0,
        },
    )
    client.post(
        "/api/v1/review-scores",
        json={
            "score_id": "s2",
            "repo_id": "repo-1",
            "dimension": "correctness",
            "score": 8.0,
        },
    )

    resp = client.get(
        "/api/v1/repositories/repo-1/review-scores/trends",
        params={"dimension": "security"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["dimension"] == "security"


def test_get_contributor_score_trends(client: TestClient) -> None:
    client.post(
        "/api/v1/review-scores",
        json={
            "score_id": "s1",
            "repo_id": "repo-1",
            "contributor_id": "user-1",
            "dimension": "performance",
            "score": 6.5,
        },
    )

    resp = client.get("/api/v1/contributors/user-1/review-scores/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["contributor_id"] == "user-1"
