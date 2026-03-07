"""Tests for workflow dispatch wiring."""

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


def test_start_workflow_dispatches_and_returns_run_id(client: TestClient) -> None:
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
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "started"
