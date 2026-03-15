"""Extract-integration-patterns workflow graph using LangGraph.

Scans a repository for integration patterns (HTTP, gRPC, message queues,
databases, file/blob storage, external APIs), classifies edges, builds a
dependency graph with coupling scores, detects antipatterns, and persists
the results.
"""

from __future__ import annotations

import os
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
import structlog

from lintel.skills_api.integration_scanning import (
    build_dependency_graph,
    detect_antipatterns,
    scan_async_integrations,
    scan_db_integrations,
    scan_external_api_calls,
    scan_file_blob_integrations,
    scan_sync_integrations,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class IntegrationPatternState(TypedDict):
    """State for the extract-integration-patterns workflow graph."""

    repository_id: str
    repo_path: str
    integration_map_id: str
    scan_results: dict[str, Any]
    classified_edges: list[dict[str, Any]]
    graph_data: dict[str, Any]  # nodes, edges, coupling_scores
    patterns: list[dict[str, Any]]
    antipatterns: list[dict[str, Any]]
    coupling_scores: list[dict[str, Any]]
    errors: list[str]
    status: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def scan_repo_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Walk the file tree, collect Python files, and run all five scanners."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("scan_repo")

    repo_path = state["repo_path"]
    errors: list[str] = []

    # --- Collect Python files ------------------------------------------------
    python_files: list[str] = []
    try:
        for root, _dirs, files in os.walk(repo_path):
            for fname in files:
                if fname.endswith(".py"):
                    python_files.append(os.path.join(root, fname))
    except OSError as exc:
        errors.append(f"File tree walk failed: {exc}")
        return {"scan_results": {}, "errors": errors, "status": "failed"}

    if not python_files:
        await tracker.append_log("scan_repo", "No Python files found — nothing to scan.")
        return {"scan_results": {}, "errors": errors, "status": "completed"}

    await tracker.append_log("scan_repo", f"Found {len(python_files)} Python files.")

    # --- Run scanners --------------------------------------------------------
    scan_results: dict[str, list[dict[str, Any]]] = {}
    scanner_map = {
        "sync_integrations": scan_sync_integrations,
        "async_integrations": scan_async_integrations,
        "db_integrations": scan_db_integrations,
        "file_blob_integrations": scan_file_blob_integrations,
        "external_api_calls": scan_external_api_calls,
    }

    for key, scanner_fn in scanner_map.items():
        try:
            scan_results[key] = await scanner_fn(python_files)
        except Exception as exc:
            logger.warning("scanner_failed", scanner=key, error=str(exc))
            errors.append(f"Scanner '{key}' failed: {exc}")
            scan_results[key] = []

    total_matches = sum(len(v) for v in scan_results.values())
    await tracker.append_log("scan_repo", f"Scanners produced {total_matches} raw matches.")
    await tracker.mark_completed("scan_repo", outputs={"total_matches": total_matches})

    return {"scan_results": scan_results, "errors": errors, "status": "scanned"}


async def classify_integrations_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Normalise raw matches into typed edge records and deduplicate."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("classify_integrations")

    scan_results: dict[str, Any] = state.get("scan_results") or {}
    seen: set[tuple[str, str, str, int]] = set()
    classified: list[dict[str, Any]] = []

    for scanner_name, results in scan_results.items():
        if not isinstance(results, list):
            continue
        for result in results:
            source_file: str = result.get("source_file", "")
            line_number: int = result.get("line_number", 0)

            # Resolve service name from directory structure
            parts = source_file.replace("\\", "/").split("/")
            source_service = parts[-2] if len(parts) >= 2 else (parts[0] if parts else "unknown")

            # Determine target from scanner-specific keys
            target: str | None = None
            for key in (
                "target_service_hint",
                "pattern_type",
                "db_type",
                "storage_type",
                "service_name",
            ):
                val = result.get(key)
                if val:
                    target = str(val)
                    break

            if target is None:
                continue

            protocol: str = result.get("protocol", "unknown")

            dedup_key = (source_file, target, protocol, line_number)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            classified.append(
                {
                    "source_service": source_service,
                    "target_service": target,
                    "protocol": protocol,
                    "source_file": source_file,
                    "line_number": line_number,
                    "scanner": scanner_name,
                    "has_retry": result.get("has_retry", False),
                }
            )

    await tracker.append_log(
        "classify_integrations",
        f"Classified {len(classified)} edges (deduped from raw matches).",
    )
    await tracker.mark_completed(
        "classify_integrations",
        outputs={"classified_count": len(classified)},
    )

    return {"classified_edges": classified, "status": "classified"}


async def build_graph_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the dependency graph and compute coupling scores."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("build_graph")

    scan_results: dict[str, Any] = state.get("scan_results") or {}

    graph_data: dict[str, Any] = await build_dependency_graph(scan_results)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    coupling_scores = graph_data.get("coupling_scores", [])

    await tracker.append_log(
        "build_graph",
        f"Graph built: {len(nodes)} nodes, {len(edges)} edges, "
        f"{len(coupling_scores)} coupling scores.",
    )
    await tracker.mark_completed(
        "build_graph",
        outputs={
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    )

    return {
        "graph_data": graph_data,
        "coupling_scores": coupling_scores,
        "status": "graph_built",
    }


async def detect_antipatterns_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Detect architectural antipatterns from the dependency graph."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("detect_antipatterns")

    graph_data: dict[str, Any] = state.get("graph_data") or {}
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    coupling_scores: list[dict[str, Any]] = state.get("coupling_scores") or []

    antipatterns: list[dict[str, Any]] = await detect_antipatterns(
        nodes=nodes,
        edges=edges,
        coupling_scores=coupling_scores,
    )

    # Separate patterns (normal edges) from antipatterns
    patterns: list[dict[str, Any]] = [
        edge
        for edge in edges
        if not any(edge.get("source") in (ap.get("affected_nodes") or []) for ap in antipatterns)
    ]

    await tracker.append_log(
        "detect_antipatterns",
        f"Found {len(antipatterns)} antipatterns, {len(patterns)} clean patterns.",
    )
    await tracker.mark_completed(
        "detect_antipatterns",
        outputs={"antipattern_count": len(antipatterns)},
    )

    return {
        "antipatterns": antipatterns,
        "patterns": patterns,
        "status": "antipatterns_detected",
    }


async def persist_results_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Structure results for persistence.

    In the future this node will call the integration-patterns-api store.
    For now it assembles the final payload and marks the workflow complete.
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("persist_results")

    payload = {
        "repository_id": state.get("repository_id", ""),
        "integration_map_id": state.get("integration_map_id", ""),
        "graph_data": state.get("graph_data", {}),
        "classified_edges": state.get("classified_edges", []),
        "patterns": state.get("patterns", []),
        "antipatterns": state.get("antipatterns", []),
        "coupling_scores": state.get("coupling_scores", []),
    }

    logger.info(
        "persist_results_payload",
        repository_id=payload["repository_id"],
        integration_map_id=payload["integration_map_id"],
        edge_count=len(payload["classified_edges"]),
        pattern_count=len(payload["patterns"]),
        antipattern_count=len(payload["antipatterns"]),
    )

    await tracker.append_log("persist_results", "Results structured for persistence.")
    await tracker.mark_completed("persist_results", outputs=payload)

    return {"status": "completed"}


async def error_node(
    state: IntegrationPatternState,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Handle workflow-level failures."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    errors = state.get("errors") or []
    logger.error("extract_integration_patterns_error", errors=errors)
    await tracker.append_log("error", f"Workflow failed with {len(errors)} error(s).")

    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Check phase helper
# ---------------------------------------------------------------------------


def _check_phase(state: IntegrationPatternState) -> str:
    """Route to error_node if the workflow has accumulated errors and status is failed."""
    if state.get("status") == "failed":
        return "error"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_extract_integration_patterns_graph() -> StateGraph[Any]:
    """Build the extract-integration-patterns workflow graph.

    Linear pipeline: scan → classify → build → detect → persist
    with error routing after each stage.
    """
    g: StateGraph[Any] = StateGraph(IntegrationPatternState)

    # Nodes
    g.add_node("scan_repo", scan_repo_node)  # type: ignore[arg-type]
    g.add_node("classify_integrations", classify_integrations_node)  # type: ignore[arg-type]
    g.add_node("build_graph", build_graph_node)  # type: ignore[arg-type]
    g.add_node("detect_antipatterns", detect_antipatterns_node)  # type: ignore[arg-type]
    g.add_node("persist_results", persist_results_node)  # type: ignore[arg-type]
    g.add_node("error", error_node)  # type: ignore[arg-type]

    # Entry
    g.set_entry_point("scan_repo")

    # Edges — linear with error routing after scan
    g.add_conditional_edges(
        "scan_repo",
        _check_phase,
        {"continue": "classify_integrations", "error": "error"},
    )
    g.add_edge("classify_integrations", "build_graph")
    g.add_edge("build_graph", "detect_antipatterns")
    g.add_edge("detect_antipatterns", "persist_results")
    g.add_edge("persist_results", END)
    g.add_edge("error", END)

    return g
