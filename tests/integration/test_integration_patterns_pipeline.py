"""Integration tests for the integration-patterns scanning pipeline.

Uses the fixture repository at tests/fixtures/sample_repo/ which contains
service_a (HTTP + DB), service_b (Kafka + S3), and service_c (tight coupling).
"""

from __future__ import annotations

from pathlib import Path

from lintel.skills_api.integration_scanning import (
    build_dependency_graph,
    detect_antipatterns,
    scan_async_integrations,
    scan_db_integrations,
    scan_external_api_calls,
    scan_file_blob_integrations,
    scan_sync_integrations,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def _fixture_files() -> list[str]:
    """Collect all .py files from the fixture sample_repo directory."""
    return [str(p) for p in FIXTURE_DIR.rglob("*.py")]


# ---------------------------------------------------------------------------
# Scanner tests
# ---------------------------------------------------------------------------


async def test_scan_sync_finds_http_calls():
    """Scan fixture files and verify requests/httpx patterns found in service_a and service_c."""
    files = _fixture_files()
    results = await scan_sync_integrations(files)

    assert len(results) >= 1

    source_files = {r["source_file"] for r in results}
    # service_a uses requests.get, service_c uses requests.get/post and httpx.AsyncClient
    service_a_hits = [r for r in results if "service_a" in r["source_file"]]
    service_c_hits = [r for r in results if "service_c" in r["source_file"]]

    assert len(service_a_hits) >= 1, "Expected requests pattern in service_a"
    assert len(service_c_hits) >= 1, "Expected requests/httpx pattern in service_c"

    # Verify protocol is http for these hits
    for hit in service_a_hits + service_c_hits:
        assert hit["protocol"] == "http"


async def test_scan_async_finds_kafka():
    """Scan fixture files and verify Kafka patterns found in service_b."""
    files = _fixture_files()
    results = await scan_async_integrations(files)

    service_b_hits = [r for r in results if "service_b" in r["source_file"]]
    assert len(service_b_hits) >= 1, "Expected Kafka pattern in service_b"

    kafka_hits = [r for r in service_b_hits if r["protocol"] == "kafka"]
    assert len(kafka_hits) >= 1, "Expected kafka protocol in service_b results"


async def test_scan_db_finds_sqlalchemy():
    """Scan fixture files and verify SQLAlchemy found in service_a."""
    files = _fixture_files()
    results = await scan_db_integrations(files)

    service_a_hits = [r for r in results if "service_a" in r["source_file"]]
    assert len(service_a_hits) >= 1, "Expected SQLAlchemy pattern in service_a"

    db_types = {r["db_type"] for r in service_a_hits}
    assert "sqlalchemy" in db_types


async def test_scan_file_blob_finds_s3():
    """Scan fixture files and verify boto3 S3 found in service_b."""
    files = _fixture_files()
    results = await scan_file_blob_integrations(files)

    service_b_hits = [r for r in results if "service_b" in r["source_file"]]
    assert len(service_b_hits) >= 1, "Expected boto3/S3 pattern in service_b"

    storage_types = {r["storage_type"] for r in service_b_hits}
    assert "s3" in storage_types


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------


async def test_build_graph_from_fixtures():
    """Run all scanners on fixture files, build dependency graph, verify structure."""
    files = _fixture_files()

    scan_results = {
        "sync_integrations": await scan_sync_integrations(files),
        "async_integrations": await scan_async_integrations(files),
        "db_integrations": await scan_db_integrations(files),
        "file_blob_integrations": await scan_file_blob_integrations(files),
        "external_api_calls": await scan_external_api_calls(files),
    }

    graph = await build_dependency_graph(scan_results)

    assert "nodes" in graph
    assert "edges" in graph
    assert "coupling_scores" in graph

    node_names = {n["name"] for n in graph["nodes"]}
    assert "service_a" in node_names, f"Expected service_a in nodes, got {node_names}"
    assert "service_b" in node_names, f"Expected service_b in nodes, got {node_names}"
    assert "service_c" in node_names, f"Expected service_c in nodes, got {node_names}"

    assert len(graph["edges"]) >= 1, "Expected at least one edge"


# ---------------------------------------------------------------------------
# Antipattern detection
# ---------------------------------------------------------------------------


async def test_detect_antipatterns_from_fixtures():
    """Build graph from fixtures, detect antipatterns, verify service_c flagged."""
    files = _fixture_files()

    scan_results = {
        "sync_integrations": await scan_sync_integrations(files),
        "async_integrations": await scan_async_integrations(files),
        "db_integrations": await scan_db_integrations(files),
        "file_blob_integrations": await scan_file_blob_integrations(files),
        "external_api_calls": await scan_external_api_calls(files),
    }

    graph = await build_dependency_graph(scan_results)
    antipatterns = await detect_antipatterns(
        nodes=graph["nodes"],
        edges=graph["edges"],
        coupling_scores=graph["coupling_scores"],
        # Lower thresholds to catch the fixture patterns
        efferent_threshold=3,
        chatty_edge_threshold=2,
    )

    assert len(antipatterns) >= 1, "Expected at least one antipattern from fixtures"

    types_found = {ap["antipattern_type"] for ap in antipatterns}
    # service_c makes many HTTP calls (tight coupling / chatty interface)
    assert "tight_coupling" in types_found or "chatty_interface" in types_found, (
        f"Expected tight_coupling or chatty_interface, got {types_found}"
    )

    # Verify service_c appears in affected nodes of at least one finding
    all_affected = []
    for ap in antipatterns:
        all_affected.extend(ap.get("affected_nodes", []))
    assert "service_c" in all_affected, f"Expected service_c in affected nodes, got {all_affected}"


# ---------------------------------------------------------------------------
# Full pipeline end-to-end
# ---------------------------------------------------------------------------


async def test_full_pipeline_end_to_end():
    """Run all scanners, build graph, detect antipatterns -- verify complete result."""
    files = _fixture_files()
    assert len(files) >= 3, f"Expected at least 3 fixture files, found {len(files)}"

    # Step 1: Run all scanners
    scan_results = {
        "sync_integrations": await scan_sync_integrations(files),
        "async_integrations": await scan_async_integrations(files),
        "db_integrations": await scan_db_integrations(files),
        "file_blob_integrations": await scan_file_blob_integrations(files),
        "external_api_calls": await scan_external_api_calls(files),
    }

    total_raw = sum(len(v) for v in scan_results.values())
    assert total_raw >= 5, f"Expected at least 5 raw matches, got {total_raw}"

    # Step 2: Build dependency graph
    graph = await build_dependency_graph(scan_results)

    assert len(graph["nodes"]) >= 3, "Expected at least 3 nodes"
    assert len(graph["edges"]) >= 3, "Expected at least 3 edges"
    assert len(graph["coupling_scores"]) >= 3, "Expected at least 3 coupling scores"

    # Step 3: Detect antipatterns
    antipatterns = await detect_antipatterns(
        nodes=graph["nodes"],
        edges=graph["edges"],
        coupling_scores=graph["coupling_scores"],
        efferent_threshold=3,
        chatty_edge_threshold=2,
    )

    # Step 4: Verify complete result structure
    result = {
        "scan_results": scan_results,
        "graph": graph,
        "antipatterns": antipatterns,
    }

    assert "scan_results" in result
    assert "graph" in result
    assert "antipatterns" in result
    assert isinstance(result["scan_results"], dict)
    assert isinstance(result["graph"], dict)
    assert isinstance(result["antipatterns"], list)

    # The fixture set should produce at least some antipatterns
    assert len(antipatterns) >= 1, "Expected at least 1 antipattern from full pipeline"

    # Every coupling score must have instability between 0 and 1
    for score in graph["coupling_scores"]:
        assert 0.0 <= score["instability"] <= 1.0, (
            f"Instability out of range for {score['service']}: {score['instability']}"
        )
