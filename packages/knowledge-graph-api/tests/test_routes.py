"""Tests for knowledge graph API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.knowledge_graph_api.routes import knowledge_graph_store_provider, router
from lintel.knowledge_graph_api.store import InMemoryKnowledgeGraphStore

if TYPE_CHECKING:
    from collections.abc import Generator

BASE = "/api/v1"


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    store = InMemoryKnowledgeGraphStore()
    knowledge_graph_store_provider.override(store)
    with TestClient(app) as c:
        yield c
    knowledge_graph_store_provider.reset()


class TestScanRepos:
    def test_scan_returns_201(self, client: TestClient) -> None:
        resp = client.post(f"{BASE}/knowledge-graph/scan", json={"repo_ids": ["repo-a"]})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"
        assert data["nodes_discovered"] == 2  # service + db
        assert data["edges_discovered"] == 1
        assert data["schemas_discovered"] == 1
        assert data["flows_discovered"] == 0  # single repo, no cross-repo flows

    def test_scan_multiple_repos(self, client: TestClient) -> None:
        resp = client.post(
            f"{BASE}/knowledge-graph/scan",
            json={"repo_ids": ["repo-a", "repo-b", "repo-c"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["nodes_discovered"] == 6  # 3 services + 3 dbs
        assert data["edges_discovered"] == 3  # 3 service->db edges
        assert data["flows_discovered"] == 2  # a->b, b->c
        assert data["schemas_discovered"] == 3

    def test_scan_empty_repos(self, client: TestClient) -> None:
        resp = client.post(f"{BASE}/knowledge-graph/scan", json={"repo_ids": []})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"
        assert data["nodes_discovered"] == 0

    def test_get_scan_status(self, client: TestClient) -> None:
        resp = client.post(f"{BASE}/knowledge-graph/scan", json={"repo_ids": ["repo-a"]})
        scan_id = resp.json()["id"]
        resp = client.get(f"{BASE}/knowledge-graph/scan/{scan_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_get_scan_not_found(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/knowledge-graph/scan/missing")
        assert resp.status_code == 404


class TestGetKnowledgeGraph:
    def test_empty_graph(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/knowledge-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["flows"] == []
        assert data["schemas"] == []

    def test_graph_after_scan(self, client: TestClient) -> None:
        client.post(
            f"{BASE}/knowledge-graph/scan",
            json={"repo_ids": ["repo-a", "repo-b"]},
        )
        resp = client.get(f"{BASE}/knowledge-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 2
        assert len(data["flows"]) == 1
        assert len(data["schemas"]) == 2


class TestListFlows:
    def test_empty_flows(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/knowledge-graph/flows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_flows_after_scan(self, client: TestClient) -> None:
        client.post(
            f"{BASE}/knowledge-graph/scan",
            json={"repo_ids": ["svc-orders", "svc-payments"]},
        )
        resp = client.get(f"{BASE}/knowledge-graph/flows")
        assert resp.status_code == 200
        flows = resp.json()
        assert len(flows) == 1
        assert flows[0]["source_service"] == "svc-orders"
        assert flows[0]["target_service"] == "svc-payments"
        assert flows[0]["transport"] == "kafka"


class TestListSchemas:
    def test_empty_schemas(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/knowledge-graph/schemas")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_schemas_after_scan(self, client: TestClient) -> None:
        client.post(
            f"{BASE}/knowledge-graph/scan",
            json={"repo_ids": ["repo-a"]},
        )
        resp = client.get(f"{BASE}/knowledge-graph/schemas")
        assert resp.status_code == 200
        schemas = resp.json()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "repo-a_schema"
        assert schemas[0]["schema_type"] == "postgres"


class TestStoreOperations:
    """Direct store tests."""

    @pytest.fixture()
    def store(self) -> InMemoryKnowledgeGraphStore:
        return InMemoryKnowledgeGraphStore()

    async def test_clear_removes_all(self, store: InMemoryKnowledgeGraphStore) -> None:
        from lintel.knowledge_graph_api.types import GraphNode

        await store.add_node(GraphNode(id="n1", kind="service", name="svc"))
        await store.clear()
        assert await store.list_nodes() == []

    async def test_get_node(self, store: InMemoryKnowledgeGraphStore) -> None:
        from lintel.knowledge_graph_api.types import GraphNode

        node = GraphNode(id="n1", kind="service", name="svc")
        await store.add_node(node)
        result = await store.get_node("n1")
        assert result is not None
        assert result.name == "svc"

    async def test_get_node_missing(self, store: InMemoryKnowledgeGraphStore) -> None:
        result = await store.get_node("missing")
        assert result is None
