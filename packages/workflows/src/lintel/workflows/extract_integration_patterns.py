"""Extract-integration-patterns workflow graph using LangGraph.

Scans a repository for integration patterns (HTTP, gRPC, message queues,
databases, file/blob storage, external APIs), classifies edges, builds a
dependency graph with coupling scores, detects antipatterns, and persists
the results.
"""

from __future__ import annotations

import os
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
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

    # Fields required by ingest + setup_workspace
    thread_ref: str
    correlation_id: str
    current_phase: str
    sanitized_messages: list[str]
    run_id: str
    project_id: str
    work_item_id: str
    repo_url: str
    repo_urls: tuple[str, ...]
    repo_branch: str
    feature_branch: str
    credential_ids: tuple[str, ...]
    sandbox_id: str | None
    workspace_path: str

    # Integration-specific fields
    repository_id: str
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
    config: RunnableConfig,
) -> dict[str, Any]:
    """List Python files inside the sandbox and run all five scanners."""
    import tempfile

    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("scan_repo")

    workspace_path = state.get("workspace_path") or state.get("repo_path", "")
    sandbox_id = state.get("sandbox_id") or ""
    errors: list[str] = []

    # Resolve sandbox manager from config (same pattern as setup_workspace)
    _configurable = config.get("configurable", {})
    sandbox_manager = _configurable.get("sandbox_manager")
    if sandbox_manager is None:
        app_state = _configurable.get("app_state")
        if app_state is not None:
            sandbox_manager = getattr(app_state, "sandbox_manager", None)

    if not sandbox_manager or not sandbox_id:
        errors.append("No sandbox available for scanning")
        await tracker.append_log(
            "scan_repo",
            f"sandbox_id={sandbox_id!r} sandbox_manager={bool(sandbox_manager)}",
        )
        await tracker.mark_completed("scan_repo", error="No sandbox available")
        return {"scan_results": {}, "errors": errors, "status": "failed"}

    # --- List Python files inside sandbox ------------------------------------
    try:
        find_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"find {workspace_path} -name '*.py' -not -path '*/__pycache__/*' -not -path '*/.venv/*'",
                workdir="/",
                timeout_seconds=30,
            ),
        )
        remote_files = [f for f in find_result.stdout.strip().splitlines() if f]
    except Exception as exc:
        errors.append(f"File listing failed: {exc}")
        await tracker.mark_completed("scan_repo", error=str(exc))
        return {"scan_results": {}, "errors": errors, "status": "failed"}

    if not remote_files:
        await tracker.append_log("scan_repo", "No Python files found — nothing to scan.")
        await tracker.mark_completed("scan_repo")
        return {"scan_results": {}, "errors": errors, "status": "completed"}

    await tracker.append_log("scan_repo", f"Found {len(remote_files)} Python files.")

    # --- Download files to a temp dir so scanners can read them --------------
    local_tmpdir = tempfile.mkdtemp(prefix="lintel_scan_")
    local_files: list[str] = []
    try:
        # Batch-read files via tar to avoid N individual reads
        tar_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"tar cf - -C / {' '.join(f.lstrip('/') for f in remote_files[:2000])}",
                workdir="/",
                timeout_seconds=60,
            ),
        )
        # Extract tar to local tmpdir
        import subprocess

        proc = subprocess.run(  # noqa: S603
            ["tar", "xf", "-", "-C", local_tmpdir],  # noqa: S607
            input=tar_result.stdout.encode() if isinstance(tar_result.stdout, str) else tar_result.stdout,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            # Fallback: read files individually
            raise RuntimeError(f"tar extract failed: {proc.stderr[:200]}")  # noqa: TRY301

        # Collect local paths
        for root, _dirs, files in os.walk(local_tmpdir):
            for fname in files:
                if fname.endswith(".py"):
                    local_files.append(os.path.join(root, fname))

    except Exception:
        logger.warning("tar_batch_download_failed_falling_back", exc_info=True)
        # Fallback: read files one by one (slower but reliable)
        for rfile in remote_files[:500]:
            try:
                cat_result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(command=f"cat {rfile}", workdir="/", timeout_seconds=5),
                )
                local_path = os.path.join(local_tmpdir, rfile.lstrip("/"))
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "w") as f:
                    f.write(cat_result.stdout)
                local_files.append(local_path)
            except Exception:
                continue

    await tracker.append_log("scan_repo", f"Downloaded {len(local_files)} files for scanning.")

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
            scan_results[key] = await scanner_fn(local_files)
        except Exception as exc:
            logger.warning("scanner_failed", scanner=key, error=str(exc))
            errors.append(f"Scanner '{key}' failed: {exc}")
            scan_results[key] = []

    # Cleanup temp dir
    import shutil

    shutil.rmtree(local_tmpdir, ignore_errors=True)

    total_matches = sum(len(v) for v in scan_results.values())
    await tracker.append_log("scan_repo", f"Scanners produced {total_matches} raw matches.")
    await tracker.mark_completed("scan_repo", outputs={"total_matches": total_matches})

    return {"scan_results": scan_results, "errors": errors, "status": "scanned"}


async def classify_integrations_node(
    state: IntegrationPatternState,
    config: RunnableConfig,
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
    config: RunnableConfig,
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
    config: RunnableConfig,
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
    config: RunnableConfig,
) -> dict[str, Any]:
    """Persist integration analysis results to the integration patterns store."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from lintel.integration_patterns_api.types import (
        AntipatternDetection,
        IntegrationEdge,
        IntegrationMap,
        PatternCatalogueEntry,
        ServiceCouplingScore,
        ServiceNode,
    )
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("persist_results")

    # Resolve the integration pattern store from app_state
    _configurable = config.get("configurable", {})
    app_state = _configurable.get("app_state")
    store = getattr(app_state, "integration_pattern_store", None) if app_state else None

    if store is None:
        await tracker.append_log("persist_results", "No integration pattern store — skipping.")
        await tracker.mark_completed("persist_results", error="No store available")
        return {"status": "failed"}

    now = datetime.now(UTC).isoformat()
    map_id = state.get("integration_map_id") or uuid4().hex
    run_id = state.get("run_id", "")
    repository_id = state.get("repository_id", "")
    graph_data = state.get("graph_data") or {}
    raw_patterns = state.get("patterns") or []
    raw_antipatterns = state.get("antipatterns") or []
    raw_coupling = state.get("coupling_scores") or []
    classified_edges = state.get("classified_edges") or []

    # 1. Create the integration map
    integration_map = IntegrationMap(
        map_id=map_id,
        repository_id=repository_id,
        workflow_run_id=run_id,
        status="completed",
        created_at=now,
        updated_at=now,
    )
    await store.create_map(integration_map)

    # 2. Persist service nodes
    raw_nodes = graph_data.get("nodes", [])
    node_id_map: dict[str, str] = {}  # service_name -> node_id
    service_nodes: list[ServiceNode] = []
    for n in raw_nodes:
        nid = uuid4().hex
        name = n.get("name", n) if isinstance(n, dict) else str(n)
        node_id_map[name] = nid
        service_nodes.append(
            ServiceNode(
                node_id=nid,
                integration_map_id=map_id,
                service_name=name,
                language=n.get("language", "python") if isinstance(n, dict) else "python",
                metadata=n if isinstance(n, dict) else {},
            )
        )
    if service_nodes:
        await store.add_nodes(service_nodes)

    # 3. Persist integration edges
    raw_edges = graph_data.get("edges", [])
    edges: list[IntegrationEdge] = []
    for e in raw_edges:
        src = e.get("source", "") if isinstance(e, dict) else ""
        tgt = e.get("target", "") if isinstance(e, dict) else ""
        edges.append(
            IntegrationEdge(
                edge_id=uuid4().hex,
                integration_map_id=map_id,
                source_node_id=node_id_map.get(src, src),
                target_node_id=node_id_map.get(tgt, tgt),
                integration_type=e.get("integration_type", "") if isinstance(e, dict) else "",
                protocol=e.get("protocol", "") if isinstance(e, dict) else "",
                metadata=e if isinstance(e, dict) else {},
            )
        )
    if edges:
        await store.add_edges(edges)

    # 4. Persist pattern catalogue entries
    pattern_counts: dict[str, int] = {}
    for p in raw_patterns:
        proto = p.get("protocol", "unknown") if isinstance(p, dict) else "unknown"
        pattern_counts[proto] = pattern_counts.get(proto, 0) + 1
    patterns: list[PatternCatalogueEntry] = [
        PatternCatalogueEntry(
            entry_id=uuid4().hex,
            integration_map_id=map_id,
            pattern_type=ptype,
            pattern_name=ptype,
            occurrences=count,
        )
        for ptype, count in pattern_counts.items()
    ]
    if patterns:
        await store.add_patterns(patterns)

    # 5. Persist antipattern detections
    detections: list[AntipatternDetection] = []
    for ap in raw_antipatterns:
        detections.append(
            AntipatternDetection(
                detection_id=uuid4().hex,
                integration_map_id=map_id,
                antipattern_type=ap.get("type", "unknown") if isinstance(ap, dict) else "unknown",
                severity=ap.get("severity", "medium") if isinstance(ap, dict) else "medium",
                affected_nodes=ap.get("affected_nodes", []) if isinstance(ap, dict) else [],
                description=ap.get("description", "") if isinstance(ap, dict) else "",
            )
        )
    if detections:
        await store.add_antipatterns(detections)

    # 6. Persist coupling scores
    scores: list[ServiceCouplingScore] = []
    for cs in raw_coupling:
        sname = cs.get("service", "") if isinstance(cs, dict) else ""
        scores.append(
            ServiceCouplingScore(
                score_id=uuid4().hex,
                integration_map_id=map_id,
                service_node_id=node_id_map.get(sname, sname),
                afferent_coupling=cs.get("afferent", 0) if isinstance(cs, dict) else 0,
                efferent_coupling=cs.get("efferent", 0) if isinstance(cs, dict) else 0,
                instability=cs.get("instability", 0.0) if isinstance(cs, dict) else 0.0,
                computed_at=now,
            )
        )
    if scores:
        await store.add_coupling_scores(scores)

    await tracker.append_log(
        "persist_results",
        f"Persisted: {len(service_nodes)} nodes, {len(edges)} edges, "
        f"{len(patterns)} patterns, {len(detections)} antipatterns, "
        f"{len(scores)} coupling scores.",
    )
    await tracker.mark_completed(
        "persist_results",
        outputs={
            "map_id": map_id,
            "node_count": len(service_nodes),
            "edge_count": len(edges),
            "pattern_count": len(patterns),
            "antipattern_count": len(detections),
            "coupling_score_count": len(scores),
        },
    )

    return {"status": "completed"}


async def error_node(
    state: IntegrationPatternState,
    config: RunnableConfig,
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

    Pipeline: ingest → setup_workspace → scan → classify → build → detect → persist
    with error routing after scan.
    """
    from lintel.workflows.nodes.ingest import ingest_message
    from lintel.workflows.nodes.setup_workspace import setup_workspace

    g: StateGraph[Any] = StateGraph(IntegrationPatternState)

    # Nodes
    g.add_node("ingest", ingest_message)  # type: ignore  # langgraph overloads
    g.add_node("setup_workspace", setup_workspace)  # type: ignore
    g.add_node("scan_repo", scan_repo_node)  # type: ignore
    g.add_node("classify_integrations", classify_integrations_node)  # type: ignore
    g.add_node("build_graph", build_graph_node)  # type: ignore
    g.add_node("detect_antipatterns", detect_antipatterns_node)  # type: ignore
    g.add_node("persist_results", persist_results_node)  # type: ignore
    g.add_node("error", error_node)  # type: ignore

    # Entry
    g.set_entry_point("ingest")

    # Edges
    g.add_edge("ingest", "setup_workspace")
    g.add_edge("setup_workspace", "scan_repo")
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
