"""Tests for process mining API routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.process_mining_api.routes import process_mining_store_provider, router
from lintel.process_mining_api.store import InMemoryProcessMiningStore


@pytest.fixture()
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    store = InMemoryProcessMiningStore()
    process_mining_store_provider.override(store)
    test_app.state.event_store = None  # no event dispatch in tests
    yield test_app  # type: ignore[misc]
    process_mining_store_provider.reset()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_create_flow_map(client: TestClient) -> None:
    resp = client.post("/flow-maps", json={"repository_id": "repo-1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["repository_id"] == "repo-1"
    assert data["status"] == "pending"
    assert "flow_map_id" in data


def test_list_flow_maps(client: TestClient) -> None:
    client.post("/flow-maps", json={"repository_id": "repo-1"})
    client.post("/flow-maps", json={"repository_id": "repo-2"})
    resp = client.get("/flow-maps")
    assert len(resp.json()) == 2

    resp = client.get("/flow-maps", params={"repository_id": "repo-1"})
    assert len(resp.json()) == 1


def test_get_flow_map_not_found(client: TestClient) -> None:
    resp = client.get("/flow-maps/nonexistent")
    assert resp.status_code == 404


def test_get_flows_empty(client: TestClient) -> None:
    resp = client.post("/flow-maps", json={"repository_id": "r1"})
    map_id = resp.json()["flow_map_id"]
    resp = client.get(f"/flow-maps/{map_id}/flows")
    assert resp.json() == []


def test_get_diagrams_empty(client: TestClient) -> None:
    resp = client.post("/flow-maps", json={"repository_id": "r1"})
    map_id = resp.json()["flow_map_id"]
    resp = client.get(f"/flow-maps/{map_id}/diagrams")
    assert resp.json() == []


def test_get_metrics_empty(client: TestClient) -> None:
    resp = client.post("/flow-maps", json={"repository_id": "r1"})
    map_id = resp.json()["flow_map_id"]
    resp = client.get(f"/flow-maps/{map_id}/metrics")
    data = resp.json()
    assert data["total_flows"] == 0
