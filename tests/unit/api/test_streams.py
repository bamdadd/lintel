"""Tests for SSE streaming endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_stream_run_events_returns_sse(client: TestClient) -> None:
    # First start a workflow to create run events
    resp = client.post(
        "/api/v1/workflows",
        json={
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "ts1",
            "workflow_type": "test_wf",
        },
    )
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    # Now stream the events
    with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as sse_resp:
        assert sse_resp.status_code == 200
        assert "text/event-stream" in sse_resp.headers["content-type"]

        lines = []
        for line in sse_resp.iter_lines():
            lines.append(line)
            # Stop after we get the end event
            if "event: end" in line:
                break

        # Should have at least PipelineRunStarted and PipelineRunCompleted events
        event_lines = [l for l in lines if l.startswith("event:")]
        assert len(event_lines) >= 2
        assert any("PipelineRunStarted" in l for l in event_lines)
        assert any("PipelineRunCompleted" in l or "end" in l for l in event_lines)
