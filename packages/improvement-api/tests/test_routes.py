"""Tests for improvement API endpoints."""

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


def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


class TestClassifyEndpoint:
    def test_classify_failures(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/improvement/classify",
            json={
                "run_id": "run-1",
                "failed_stages": [
                    {"name": "test", "error": "5 failed, 3 passed", "logs": []},
                    {"name": "deploy", "error": "docker container failed", "logs": []},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run-1"
        assert len(data["failures"]) == 2
        assert data["class_distribution"]["test_failure"] == 1
        assert data["class_distribution"]["sandbox"] == 1

    def test_classify_empty_stages(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/improvement/classify",
            json={"run_id": "run-empty", "failed_stages": []},
        )
        assert resp.status_code == 200
        assert resp.json()["primary_class"] == "unknown"

    def test_classify_silent_failure(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/improvement/classify",
            json={
                "run_id": "run-silent",
                "failed_stages": [{"name": "build", "error": "", "logs": []}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["failures"][0]["failure_class"] == "silent_failure"


class TestOverfitCheckEndpoint:
    def test_rejects_single_task(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/improvement/overfit-check",
            json={
                "target_class": "test_failure",
                "class_pass_rate_before": 0.5,
                "class_pass_rate_after": 1.0,
                "affected_runs": 1,
                "overall_pass_rate_before": 0.8,
                "overall_pass_rate_after": 0.85,
            },
        )
        assert resp.status_code == 200
        assert not resp.json()["passed"]

    def test_accepts_valid_improvement(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/improvement/overfit-check",
            json={
                "target_class": "sandbox",
                "class_pass_rate_before": 0.3,
                "class_pass_rate_after": 0.8,
                "affected_runs": 5,
                "overall_pass_rate_before": 0.7,
                "overall_pass_rate_after": 0.8,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["passed"]


class TestLedgerCRUD:
    def test_create_and_get(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "imp-1",
                "project_id": "proj-1",
                "iteration": 1,
                "target_class": "test_failure",
                "description": "Fix flaky test pattern",
                "pass_rate_before": 0.6,
                "pass_rate_after": 0.85,
                "cost_usd": 0.50,
                "decision": "keep",
                "failure_distribution_before": {"test_failure": 4, "sandbox": 1},
                "affected_run_ids": ["r1", "r2", "r3"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entry_id"] == "imp-1"
        assert data["target_class"] == "test_failure"
        assert data["pass_rate_before"] == 0.6

        get_resp = client.get("/api/v1/improvement/ledger/imp-1")
        assert get_resp.status_code == 200
        assert get_resp.json()["description"] == "Fix flaky test pattern"

    def test_create_duplicate(self, client: TestClient) -> None:
        _create_project(client)
        payload = {
            "entry_id": "imp-dup",
            "project_id": "proj-1",
            "iteration": 1,
            "target_class": "sandbox",
        }
        assert client.post("/api/v1/improvement/ledger", json=payload).status_code == 201
        assert client.post("/api/v1/improvement/ledger", json=payload).status_code == 409

    def test_list_all(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "a",
                "project_id": "proj-1",
                "iteration": 1,
                "target_class": "sandbox",
            },
        )
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "b",
                "project_id": "proj-1",
                "iteration": 2,
                "target_class": "timeout",
            },
        )
        resp = client.get("/api/v1/improvement/ledger")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_by_project(self, client: TestClient) -> None:
        _create_project(client, "p1")
        _create_project(client, "p2")
        client.post(
            "/api/v1/improvement/ledger",
            json={"entry_id": "x", "project_id": "p1", "iteration": 1, "target_class": "auth"},
        )
        client.post(
            "/api/v1/improvement/ledger",
            json={"entry_id": "y", "project_id": "p2", "iteration": 1, "target_class": "auth"},
        )
        resp = client.get("/api/v1/improvement/ledger", params={"project_id": "p1"})
        assert len(resp.json()) == 1

    def test_update(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "up",
                "project_id": "proj-1",
                "iteration": 1,
                "target_class": "sandbox",
            },
        )
        resp = client.patch(
            "/api/v1/improvement/ledger/up",
            json={"decision": "discard", "overfit_reason": "single_task_fix"},
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "discard"

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/improvement/ledger/missing", json={"decision": "keep"})
        assert resp.status_code == 404

    def test_delete(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "del",
                "project_id": "proj-1",
                "iteration": 1,
                "target_class": "sandbox",
            },
        )
        assert client.delete("/api/v1/improvement/ledger/del").status_code == 204
        assert client.get("/api/v1/improvement/ledger/del").status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/improvement/ledger/missing").status_code == 404

    def test_get_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/improvement/ledger/missing").status_code == 404


class TestDistributionEndpoint:
    def test_empty_distribution(self, client: TestClient) -> None:
        resp = client.get("/api/v1/improvement/distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 0
        assert data["pass_rate"] == 0.0

    def test_distribution_with_entries(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "d1",
                "project_id": "proj-1",
                "iteration": 1,
                "target_class": "test_failure",
                "decision": "keep",
                "failure_distribution_before": {"test_failure": 3, "sandbox": 1},
            },
        )
        client.post(
            "/api/v1/improvement/ledger",
            json={
                "entry_id": "d2",
                "project_id": "proj-1",
                "iteration": 2,
                "target_class": "sandbox",
                "decision": "discard",
                "failure_distribution_before": {"sandbox": 2},
            },
        )
        resp = client.get("/api/v1/improvement/distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 2
        assert data["class_counts"]["test_failure"] == 3
        assert data["class_counts"]["sandbox"] == 3
