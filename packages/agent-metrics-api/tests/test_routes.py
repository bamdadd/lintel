"""Tests for agent-metrics API."""

from fastapi.testclient import TestClient


class TestAgentMetricsSummary:
    def test_summary_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-metrics/summary")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_summary_aggregates_by_agent(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "coder-1", "metric_type": "pr_merged", "value": 1},
        )
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "coder-1", "metric_type": "pr_merged", "value": 2},
        )
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "reviewer-1", "metric_type": "review_completed"},
        )
        resp = client.get("/api/v1/agent-metrics/summary")
        data = resp.json()
        assert data["coder-1"]["pr_merged"] == 3
        assert data["reviewer-1"]["review_completed"] == 1


class TestAgentMetricsHistory:
    def test_history_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent-metrics/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_returns_recorded_events(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "coder-1", "metric_type": "lines_changed", "value": 150},
        )
        resp = client.get("/api/v1/agent-metrics/history")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["agent_id"] == "coder-1"
        assert data[0]["value"] == 150

    def test_history_filter_by_agent(self, client: TestClient) -> None:
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "coder-1", "metric_type": "pr_merged"},
        )
        client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "reviewer-1", "metric_type": "review_completed"},
        )
        resp = client.get("/api/v1/agent-metrics/history?agent_id=coder-1")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["agent_id"] == "coder-1"


class TestRecordMetric:
    def test_record_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/agent-metrics/record",
            json={"agent_id": "coder-1", "metric_type": "pr_merged"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_id"] == "coder-1"
        assert data["metric_type"] == "pr_merged"
        assert "event_id" in data
        assert "recorded_at" in data

    def test_record_with_metadata(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/agent-metrics/record",
            json={
                "agent_id": "coder-1",
                "metric_type": "pr_merged",
                "metadata": {"pr_url": "https://github.com/org/repo/pull/42"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["metadata"]["pr_url"] == "https://github.com/org/repo/pull/42"
