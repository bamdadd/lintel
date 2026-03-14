"""Tests for experimentation API endpoints (KPIs, experiments, compliance metrics)."""

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


def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


# ======================== KPIs ========================


class TestKPIsAPI:
    def test_create_kpi(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/kpis",
            json={
                "kpi_id": "kpi-1",
                "project_id": "proj-1",
                "name": "Code Coverage",
                "target_value": "90",
                "current_value": "75",
                "unit": "%",
                "direction": "increase",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_value"] == "90"
        assert data["direction"] == "increase"

    def test_update_kpi_value(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/kpis",
            json={"kpi_id": "kpi-2", "project_id": "proj-1", "name": "MTTR", "current_value": "45"},
        )
        resp = client.patch("/api/v1/kpis/kpi-2", json={"current_value": "30"})
        assert resp.status_code == 200
        assert resp.json()["current_value"] == "30"

    def test_delete_kpi(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/kpis", json={"kpi_id": "kpi-3", "project_id": "proj-1", "name": "Delete Me"}
        )
        assert client.delete("/api/v1/kpis/kpi-3").status_code == 204


# ======================== EXPERIMENTS ========================


class TestExperimentsAPI:
    def test_create_experiment(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/experiments",
            json={
                "experiment_id": "exp-1",
                "project_id": "proj-1",
                "name": "AI Code Review",
                "hypothesis": "AI review reduces bug rate by 30%",
                "status": "running",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["hypothesis"] == "AI review reduces bug rate by 30%"
        assert data["status"] == "running"

    def test_update_experiment_outcome(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/experiments",
            json={"experiment_id": "exp-2", "project_id": "proj-1", "name": "Exp 2"},
        )
        resp = client.patch(
            "/api/v1/experiments/exp-2",
            json={"status": "completed", "outcome": "Positive: 35% reduction"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_delete_experiment(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/experiments",
            json={"experiment_id": "exp-3", "project_id": "proj-1", "name": "Delete Me"},
        )
        assert client.delete("/api/v1/experiments/exp-3").status_code == 204


# ======================== COMPLIANCE METRICS ========================


class TestComplianceMetricsAPI:
    def test_create_compliance_metric(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/compliance-metrics",
            json={
                "metric_id": "met-1",
                "project_id": "proj-1",
                "name": "Vulnerability Count",
                "value": "3",
                "unit": "count",
                "source": "automated",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["source"] == "automated"

    def test_delete_compliance_metric(self, client: TestClient) -> None:
        _create_project(client)
        client.post(
            "/api/v1/compliance-metrics",
            json={"metric_id": "met-2", "project_id": "proj-1", "name": "Delete Me"},
        )
        assert client.delete("/api/v1/compliance-metrics/met-2").status_code == 204
