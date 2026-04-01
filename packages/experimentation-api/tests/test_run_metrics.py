"""Tests for run metrics, strategy mutations, and tournament selection."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app
from lintel.experimentation_api.run_metrics import suggest_mutations_for_failure

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


# ======================== RUN METRICS ========================


class TestRunMetricsAPI:
    def test_create_run_metric(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/run-metrics",
            json={
                "run_metric_id": "rm-1",
                "run_id": "run-1",
                "experiment_id": "exp-1",
                "metric_name": "duration_ms",
                "value": 1500.0,
                "unit": "ms",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric_name"] == "duration_ms"
        assert data["value"] == 1500.0

    def test_list_run_metrics_by_run_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/run-metrics",
            json={"run_metric_id": "rm-2", "run_id": "run-a", "metric_name": "tests_passed"},
        )
        client.post(
            "/api/v1/run-metrics",
            json={"run_metric_id": "rm-3", "run_id": "run-b", "metric_name": "tests_passed"},
        )
        resp = client.get("/api/v1/run-metrics", params={"run_id": "run-a"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_run_metric(self, client: TestClient) -> None:
        client.post(
            "/api/v1/run-metrics",
            json={"run_metric_id": "rm-4", "run_id": "run-1", "metric_name": "coverage"},
        )
        resp = client.get("/api/v1/run-metrics/rm-4")
        assert resp.status_code == 200
        assert resp.json()["run_metric_id"] == "rm-4"

    def test_get_run_metric_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/run-metrics/nonexistent")
        assert resp.status_code == 404

    def test_delete_run_metric(self, client: TestClient) -> None:
        client.post(
            "/api/v1/run-metrics",
            json={"run_metric_id": "rm-5", "run_id": "run-1"},
        )
        assert client.delete("/api/v1/run-metrics/rm-5").status_code == 204

    def test_batch_create_run_metrics(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/run-metrics/batch",
            json={
                "metrics": [
                    {"run_metric_id": "rm-b1", "run_id": "run-x", "metric_name": "a"},
                    {"run_metric_id": "rm-b2", "run_id": "run-x", "metric_name": "b"},
                ]
            },
        )
        assert resp.status_code == 201
        assert len(resp.json()) == 2


# ======================== STRATEGY MUTATIONS ========================


class TestStrategyMutationsAPI:
    def test_create_strategy_mutation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/strategy-mutations",
            json={
                "mutation_id": "mut-1",
                "experiment_id": "exp-1",
                "source_run_id": "run-1",
                "strategy": "increase_timeout",
                "description": "Double the timeout",
                "config_patch": {"timeout_multiplier": 2.0},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["strategy"] == "increase_timeout"

    def test_list_mutations_by_experiment(self, client: TestClient) -> None:
        client.post(
            "/api/v1/strategy-mutations",
            json={"mutation_id": "mut-2", "experiment_id": "exp-a", "source_run_id": "run-1"},
        )
        client.post(
            "/api/v1/strategy-mutations",
            json={"mutation_id": "mut-3", "experiment_id": "exp-b", "source_run_id": "run-2"},
        )
        resp = client.get("/api/v1/strategy-mutations", params={"experiment_id": "exp-a"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_mutation_applied(self, client: TestClient) -> None:
        client.post(
            "/api/v1/strategy-mutations",
            json={"mutation_id": "mut-4", "experiment_id": "exp-1", "source_run_id": "run-1"},
        )
        resp = client.patch("/api/v1/strategy-mutations/mut-4", json={"applied": True})
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

    def test_get_mutation_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/strategy-mutations/nonexistent")
        assert resp.status_code == 404


# ======================== TOURNAMENT SELECTION ========================


class TestTournamentAPI:
    def test_run_tournament_maximize(self, client: TestClient) -> None:
        # Create metrics for two runs
        client.post(
            "/api/v1/run-metrics",
            json={
                "run_metric_id": "t-rm-1",
                "run_id": "run-a",
                "metric_name": "score",
                "value": 85.0,
            },
        )
        client.post(
            "/api/v1/run-metrics",
            json={
                "run_metric_id": "t-rm-2",
                "run_id": "run-b",
                "metric_name": "score",
                "value": 92.0,
            },
        )

        resp = client.post(
            "/api/v1/tournaments",
            json={
                "tournament_id": "tour-1",
                "experiment_id": "exp-1",
                "task_key": "code-review",
                "run_ids": ["run-a", "run-b"],
                "metric_name": "score",
                "direction": "maximize",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["winning_run_id"] == "run-b"
        assert data["scores"]["run-b"] == 92.0

    def test_run_tournament_minimize(self, client: TestClient) -> None:
        client.post(
            "/api/v1/run-metrics",
            json={
                "run_metric_id": "t-rm-3",
                "run_id": "run-c",
                "metric_name": "errors",
                "value": 5.0,
            },
        )
        client.post(
            "/api/v1/run-metrics",
            json={
                "run_metric_id": "t-rm-4",
                "run_id": "run-d",
                "metric_name": "errors",
                "value": 2.0,
            },
        )

        resp = client.post(
            "/api/v1/tournaments",
            json={
                "tournament_id": "tour-2",
                "experiment_id": "exp-1",
                "run_ids": ["run-c", "run-d"],
                "metric_name": "errors",
                "direction": "minimize",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["winning_run_id"] == "run-d"

    def test_tournament_no_matching_metrics(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/tournaments",
            json={
                "tournament_id": "tour-3",
                "experiment_id": "exp-1",
                "run_ids": ["run-x"],
                "metric_name": "nonexistent",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["winning_run_id"] == ""

    def test_list_tournaments(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tournaments",
            json={
                "tournament_id": "tour-4",
                "experiment_id": "exp-2",
                "run_ids": [],
                "metric_name": "score",
            },
        )
        resp = client.get("/api/v1/tournaments", params={"experiment_id": "exp-2"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_tournament(self, client: TestClient) -> None:
        client.post(
            "/api/v1/tournaments",
            json={
                "tournament_id": "tour-5",
                "experiment_id": "exp-1",
                "run_ids": [],
                "metric_name": "x",
            },
        )
        resp = client.get("/api/v1/tournaments/tour-5")
        assert resp.status_code == 200

    def test_get_tournament_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tournaments/nonexistent")
        assert resp.status_code == 404


# ======================== SUGGEST MUTATIONS (pure function) ========================


class TestSuggestMutations:
    def test_timeout_failure(self) -> None:
        mutations = suggest_mutations_for_failure("run-1", "exp-1", "Operation timeout exceeded")
        assert len(mutations) >= 1
        assert any(m.strategy.value == "increase_timeout" for m in mutations)

    def test_concurrency_failure(self) -> None:
        mutations = suggest_mutations_for_failure("run-1", "exp-1", "Resource contention detected")
        assert any(m.strategy.value == "reduce_concurrency" for m in mutations)

    def test_model_failure(self) -> None:
        mutations = suggest_mutations_for_failure("run-1", "exp-1", "LLM rate limit hit")
        assert any(m.strategy.value == "switch_model" for m in mutations)

    def test_generic_failure_suggests_retry(self) -> None:
        mutations = suggest_mutations_for_failure("run-1", "exp-1", "Unknown error")
        assert len(mutations) == 1
        assert mutations[0].strategy.value == "add_retry"

    def test_mutation_has_config_patch(self) -> None:
        mutations = suggest_mutations_for_failure("run-1", "exp-1", "timeout")
        assert mutations[0].config_patch is not None
