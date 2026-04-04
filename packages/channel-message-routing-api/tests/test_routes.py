"""Tests for channel message routing API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_create_routing_rule(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/channel-routing/rules",
        json={
            "connection_id": "conn-1",
            "workflow_definition_id": "wf-1",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["connection_id"] == "conn-1"
    assert data["workflow_definition_id"] == "wf-1"
    assert data["channel_pattern"] == "*"
    assert data["enabled"] is True


def test_create_duplicate_returns_409(client: TestClient) -> None:
    payload = {
        "rule_id": "dup-id",
        "connection_id": "conn-1",
        "workflow_definition_id": "wf-1",
    }
    resp = client.post("/api/v1/channel-routing/rules", json=payload)
    assert resp.status_code == 201
    resp2 = client.post("/api/v1/channel-routing/rules", json=payload)
    assert resp2.status_code == 409


def test_list_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/channel-routing/rules")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_created(client: TestClient) -> None:
    client.post(
        "/api/v1/channel-routing/rules",
        json={"connection_id": "c1", "workflow_definition_id": "wf-1"},
    )
    resp = client.get("/api/v1/channel-routing/rules")
    assert len(resp.json()) == 1


def test_list_filter_by_connection_id(client: TestClient) -> None:
    client.post(
        "/api/v1/channel-routing/rules",
        json={"connection_id": "c1", "workflow_definition_id": "wf-1"},
    )
    client.post(
        "/api/v1/channel-routing/rules",
        json={"connection_id": "c2", "workflow_definition_id": "wf-2"},
    )
    resp = client.get("/api/v1/channel-routing/rules", params={"connection_id": "c1"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["connection_id"] == "c1"


def test_get_existing(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/channel-routing/rules",
        json={"connection_id": "c1", "workflow_definition_id": "wf-1"},
    )
    rule_id = create_resp.json()["rule_id"]
    resp = client.get(f"/api/v1/channel-routing/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["rule_id"] == rule_id


def test_get_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/channel-routing/rules/nonexistent")
    assert resp.status_code == 404


def test_delete_existing(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/channel-routing/rules",
        json={"connection_id": "c1", "workflow_definition_id": "wf-1"},
    )
    rule_id = create_resp.json()["rule_id"]
    resp = client.delete(f"/api/v1/channel-routing/rules/{rule_id}")
    assert resp.status_code == 204


def test_delete_missing_returns_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/channel-routing/rules/nonexistent")
    assert resp.status_code == 404


def test_resolve_matching_rule(client: TestClient) -> None:
    client.post(
        "/api/v1/channel-routing/rules",
        json={
            "connection_id": "conn-1",
            "channel_pattern": "#general",
            "message_pattern": "deploy",
            "workflow_definition_id": "wf-deploy",
        },
    )
    resp = client.post(
        "/api/v1/channel-routing/resolve",
        json={
            "connection_id": "conn-1",
            "channel": "#general",
            "message": "please deploy this",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["match"] is not None
    assert resp.json()["match"]["workflow_definition_id"] == "wf-deploy"


def test_resolve_no_match(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/channel-routing/resolve",
        json={
            "connection_id": "conn-1",
            "channel": "#general",
            "message": "hello",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["match"] is None
