"""Unit tests for each LangGraph node in the extract-integration-patterns workflow.

Each test calls the node function directly with a constructed state dict
and mocked dependencies (StageTracker, scanners, etc.).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lintel.workflows.extract_integration_patterns import (
    IntegrationPatternState,
    build_extract_integration_patterns_graph,
    build_graph_node,
    classify_integrations_node,
    detect_antipatterns_node,
    persist_results_node,
    scan_repo_node,
)


def _make_state(**overrides: object) -> IntegrationPatternState:
    base: dict = {
        "repository_id": "repo-1",
        "repo_path": "/tmp/test-repo",
        "integration_map_id": "",
        "scan_results": {},
        "resilience_index": {},
        "classified_edges": [],
        "graph_data": {},
        "patterns": [],
        "antipatterns": [],
        "coupling_scores": [],
        "errors": [],
        "status": "pending",
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def _make_config() -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": "test-thread"}}


def _mock_stage_tracker() -> MagicMock:
    """Return a mock StageTracker that silently accepts all calls."""
    tracker = MagicMock()
    tracker.mark_running = AsyncMock()
    tracker.mark_completed = AsyncMock()
    tracker.append_log = AsyncMock()
    return tracker


# ---------------------------------------------------------------------------
# scan_repo_node
# ---------------------------------------------------------------------------


async def test_scan_repo_node_no_sandbox_returns_failed() -> None:
    """Without a sandbox, scan_repo_node should return failed status."""
    state = _make_state(repo_path="/tmp/test-repo")
    config = _make_config()

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await scan_repo_node(state, config)

    assert result["status"] == "failed"
    assert result["scan_results"] == {}
    assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# classify_integrations_node
# ---------------------------------------------------------------------------


async def test_classify_integrations_node_deduplicates() -> None:
    """Provide duplicate raw matches in scan_results and verify deduplication."""
    duplicate_match = {
        "source_file": "/repo/service_a/main.py",
        "target_service_hint": "requests",
        "protocol": "http",
        "line_number": 5,
        "match_text": "requests.get(",
    }
    scan_results = {
        "sync_integrations": [duplicate_match, duplicate_match],
        "external_api_calls": [duplicate_match],
    }
    state = _make_state(scan_results=scan_results)
    config = _make_config()

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await classify_integrations_node(state, config)

    classified = result["classified_edges"]
    # Three identical records should collapse to one after dedup
    assert len(classified) == 1
    assert classified[0]["source_service"] == "service_a"
    assert classified[0]["target_service"] == "requests"
    assert result["status"] == "classified"


# ---------------------------------------------------------------------------
# build_graph_node
# ---------------------------------------------------------------------------


async def test_build_graph_node_computes_coupling() -> None:
    """Provide classified_edges via scan_results and verify graph_data structure."""
    scan_results = {
        "sync_integrations": [
            {
                "source_file": "/repo/service_a/main.py",
                "target_service_hint": "payment_api",
                "protocol": "http",
                "line_number": 10,
                "match_text": "requests.get(",
            },
            {
                "source_file": "/repo/service_b/main.py",
                "target_service_hint": "order_api",
                "protocol": "http",
                "line_number": 5,
                "match_text": "httpx.AsyncClient(",
            },
        ],
    }
    state = _make_state(scan_results=scan_results)
    config = _make_config()

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await build_graph_node(state, config)

    graph_data = result["graph_data"]
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert "coupling_scores" in graph_data

    node_names = {n["name"] for n in graph_data["nodes"]}
    assert "service_a" in node_names or "service_b" in node_names

    coupling_scores = result["coupling_scores"]
    assert len(coupling_scores) >= 1
    # Each coupling score must have the expected keys
    for score in coupling_scores:
        assert "service" in score
        assert "afferent_coupling" in score
        assert "efferent_coupling" in score
        assert "instability" in score

    assert result["status"] == "graph_built"


# ---------------------------------------------------------------------------
# detect_antipatterns_node
# ---------------------------------------------------------------------------


async def test_detect_antipatterns_node_finds_issues() -> None:
    """Provide a graph with a known antipattern and verify it is detected."""
    # Build a graph with tight coupling: one service has efferent > threshold
    nodes = [{"name": "svc_chatty"}, {"name": "target_a"}, {"name": "target_b"}]
    edges = [
        {
            "source": "svc_chatty",
            "target": "target_a",
            "protocol": "http",
            "integration_type": "sync",
            "call_count": 4,
        },
        {
            "source": "svc_chatty",
            "target": "target_b",
            "protocol": "http",
            "integration_type": "sync",
            "call_count": 2,
        },
    ]
    coupling_scores = [
        {
            "service": "svc_chatty",
            "afferent_coupling": 0,
            "efferent_coupling": 6,
            "instability": 1.0,
        },
        {
            "service": "target_a",
            "afferent_coupling": 4,
            "efferent_coupling": 0,
            "instability": 0.0,
        },
        {
            "service": "target_b",
            "afferent_coupling": 2,
            "efferent_coupling": 0,
            "instability": 0.0,
        },
    ]

    state = _make_state(
        graph_data={"nodes": nodes, "edges": edges, "coupling_scores": coupling_scores},
        coupling_scores=coupling_scores,
    )
    config = _make_config()

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await detect_antipatterns_node(state, config)

    antipatterns = result["antipatterns"]
    assert len(antipatterns) >= 1
    types_found = {ap["antipattern_type"] for ap in antipatterns}
    # With efferent=6 (> default threshold 5) we expect tight_coupling,
    # and 4 edges svc_chatty->target_a (> default chatty threshold 3) triggers chatty_interface,
    # plus missing_retry for HTTP edges without retry.
    assert "tight_coupling" in types_found or "chatty_interface" in types_found
    assert result["status"] == "antipatterns_detected"


# ---------------------------------------------------------------------------
# persist_results_node
# ---------------------------------------------------------------------------


async def test_persist_results_node_no_store_returns_failed() -> None:
    """Without a store, persist_results_node should return failed status."""
    state = _make_state(
        repository_id="repo-42",
        integration_map_id="map-1",
        graph_data={"nodes": [{"name": "a"}], "edges": [], "coupling_scores": []},
        classified_edges=[{"source_service": "a", "target_service": "b"}],
        patterns=[{"pattern_type": "event_driven", "pattern_name": "Event-Driven"}],
        antipatterns=[{"antipattern_type": "tight_coupling"}],
        coupling_scores=[{"service": "a", "efferent_coupling": 10}],
    )
    config = _make_config()

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await persist_results_node(state, config)

    # No store configured → fails gracefully
    assert result["status"] == "failed"


async def test_persist_results_node_with_store() -> None:
    """With a mock store, persist_results_node should return 'completed'."""
    state = _make_state(
        repository_id="repo-42",
        integration_map_id="map-1",
        graph_data={"nodes": [{"name": "a"}], "edges": [], "coupling_scores": []},
        classified_edges=[{"source_service": "a", "target_service": "b"}],
        patterns=[{"pattern_type": "event_driven", "pattern_name": "Event-Driven"}],
        antipatterns=[{"antipattern_type": "tight_coupling", "severity": "high"}],
        coupling_scores=[{"service": "a", "efferent_coupling": 10}],
    )

    mock_store = AsyncMock()
    mock_app_state = MagicMock()
    mock_app_state.integration_pattern_store = mock_store

    config: dict = {"configurable": {"thread_id": "test-thread", "app_state": mock_app_state}}

    with patch(
        "lintel.workflows.nodes._stage_tracking.StageTracker",
        return_value=_mock_stage_tracker(),
    ):
        result = await persist_results_node(state, config)

    assert result["status"] == "completed"
    mock_store.create_map.assert_called_once()
    mock_store.add_nodes.assert_called_once()


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------


def test_graph_compiles() -> None:
    """build_extract_integration_patterns_graph returns a compilable graph."""
    graph = build_extract_integration_patterns_graph()
    assert graph is not None

    compiled = graph.compile()
    assert compiled is not None
    # The compiled graph should expose an invoke or ainvoke method
    assert hasattr(compiled, "ainvoke") or hasattr(compiled, "invoke")
