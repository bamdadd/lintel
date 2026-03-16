"""Tests for building the service dependency graph from scan results."""

import pytest

from lintel.skills_api.integration_scanning import build_dependency_graph


@pytest.mark.asyncio
async def test_builds_nodes_from_scan_results() -> None:
    scan_results = {
        "sync_integrations": [
            {
                "source_file": "/app/order_service/client.py",
                "target_service_hint": "payment_api",
                "protocol": "http",
                "line_number": 10,
                "match_text": "requests.get(",
            },
        ],
        "db_integrations": [
            {
                "source_file": "/app/order_service/models.py",
                "db_type": "sqlalchemy",
                "client_pattern": "create_engine",
                "line_number": 5,
                "match_text": "create_engine(",
            },
        ],
    }

    graph = await build_dependency_graph(scan_results)

    node_names = {n["name"] for n in graph["nodes"]}
    assert "order_service" in node_names
    assert "payment_api" in node_names
    assert "PostgreSQL" in node_names  # sqlalchemy normalised to PostgreSQL
    assert len(graph["edges"]) == 2


@pytest.mark.asyncio
async def test_computes_coupling_scores() -> None:
    scan_results = {
        "sync_integrations": [
            {
                "source_file": "/app/gateway/handler.py",
                "target_service_hint": "users",
                "protocol": "http",
                "line_number": 1,
                "match_text": "requests.get(",
            },
            {
                "source_file": "/app/gateway/handler.py",
                "target_service_hint": "orders",
                "protocol": "http",
                "line_number": 2,
                "match_text": "requests.post(",
            },
        ],
    }

    graph = await build_dependency_graph(scan_results)

    scores_by_service = {s["service"]: s for s in graph["coupling_scores"]}
    assert "gateway" in scores_by_service
    gateway = scores_by_service["gateway"]
    assert gateway["efferent_coupling"] == 2
    assert gateway["afferent_coupling"] == 0
    assert gateway["instability"] == 1.0

    users = scores_by_service["users"]
    assert users["afferent_coupling"] == 1
    assert users["efferent_coupling"] == 0
    assert users["instability"] == 0.0


@pytest.mark.asyncio
async def test_empty_results() -> None:
    graph = await build_dependency_graph({})

    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["coupling_scores"] == []
