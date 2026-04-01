"""Tests for review-reports-api routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_create_review_report(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/review-reports",
        json={
            "pipeline_run_id": "run-1",
            "repo_id": "repo-1",
            "contributor_id": "user-1",
            "commit_shas": ["abc123"],
            "aggregate_scores": {"correctness": 8.5, "security": 7.0},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["repo_id"] == "repo-1"
    assert data["aggregate_scores"]["correctness"] == 8.5


def test_get_review_report(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/review-reports",
        json={
            "report_id": "rpt-1",
            "pipeline_run_id": "run-1",
            "repo_id": "repo-1",
        },
    )
    assert create_resp.status_code == 201

    resp = client.get("/api/v1/review-reports/rpt-1")
    assert resp.status_code == 200
    assert resp.json()["report_id"] == "rpt-1"


def test_get_review_report_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/review-reports/nonexistent")
    assert resp.status_code == 404


def test_list_review_reports_by_repo(client: TestClient) -> None:
    client.post(
        "/api/v1/review-reports",
        json={
            "report_id": "rpt-a",
            "pipeline_run_id": "run-1",
            "repo_id": "repo-1",
        },
    )
    client.post(
        "/api/v1/review-reports",
        json={
            "report_id": "rpt-b",
            "pipeline_run_id": "run-2",
            "repo_id": "repo-2",
        },
    )

    resp = client.get("/api/v1/repositories/repo-1/review-reports")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["report_id"] == "rpt-a"
