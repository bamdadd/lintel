"""Tests for SSE streaming endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_stream_run_events_returns_sse(client: TestClient) -> None:
    # Start a code workflow without repo_url — pre-flight will fail,
    # but the run still emits WorkflowQueued + PipelineRunFailed events.
    resp = client.post(
        "/api/v1/workflows",
        json={
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "ts1",
            "workflow_type": "feature_to_pr",
        },
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    # Now stream the events — should receive at least the queued + failed events
    with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as sse_resp:
        assert sse_resp.status_code == 200
        assert "text/event-stream" in sse_resp.headers["content-type"]

        lines = []
        for line in sse_resp.iter_lines():
            lines.append(line)
            if "event: end" in line:
                break

        event_lines = [line for line in lines if line.startswith("event:")]
        assert len(event_lines) >= 1
        assert any(
            "WorkflowQueued" in evt or "PipelineRunFailed" in evt or "end" in evt
            for evt in event_lines
        )
