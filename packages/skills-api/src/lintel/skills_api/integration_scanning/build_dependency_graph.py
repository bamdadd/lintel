"""Build a service dependency graph from aggregated scan results."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

import structlog

logger = structlog.get_logger(__name__)


def _infer_service_name(file_path: str) -> str:
    """Infer a service name from a file path using a directory heuristic.

    Uses the parent directory name of the source file as the service name.
    Falls back to the file stem if no parent directory is available.
    """
    parts = PurePosixPath(file_path).parts
    if len(parts) >= 2:
        return parts[-2]
    return PurePosixPath(file_path).stem


def _extract_target(result: dict) -> str | None:
    """Extract the target service / system name from a single scan result."""
    # Each scanner uses a different key for the target hint.
    for key in (
        "target_service_hint",
        "pattern_type",
        "db_type",
        "storage_type",
        "service_name",
    ):
        value = result.get(key)
        if value:
            return str(value)
    return None


def _extract_protocol(result: dict) -> str:
    """Extract the protocol from a scan result, falling back to 'unknown'."""
    return str(result.get("protocol", "unknown"))


async def build_dependency_graph(scan_results: dict) -> dict:
    """Build a dependency graph from aggregated scan results.

    Args:
        scan_results: Dict whose keys are scanner names and values are
            the lists returned by the corresponding scanner function.
            Expected keys (all optional):
              - sync_integrations
              - async_integrations
              - db_integrations
              - file_blob_integrations
              - external_api_calls

    Returns:
        Dict with three top-level keys:
          - nodes: list of ``{name: str}``
          - edges: list of ``{source, target, protocol, source_file, line_number}``
          - coupling_scores: list of ``{service, afferent_coupling,
            efferent_coupling, instability}``
    """
    all_results: list[dict] = []
    for _scanner_name, results in scan_results.items():
        if isinstance(results, list):
            all_results.extend(results)

    # ---- Build edges ---------------------------------------------------------
    edges: list[dict] = []
    service_names: set[str] = set()

    for result in all_results:
        source_file = result.get("source_file", "")
        source_service = _infer_service_name(source_file)
        target = _extract_target(result)
        if target is None:
            continue

        service_names.add(source_service)
        service_names.add(target)

        edges.append(
            {
                "source": source_service,
                "target": target,
                "protocol": _extract_protocol(result),
                "source_file": source_file,
                "line_number": result.get("line_number", 0),
            }
        )

    # ---- Build nodes ---------------------------------------------------------
    nodes: list[dict] = [{"name": name} for name in sorted(service_names)]

    # ---- Compute coupling scores ---------------------------------------------
    afferent: dict[str, int] = defaultdict(int)
    efferent: dict[str, int] = defaultdict(int)

    for edge in edges:
        efferent[edge["source"]] += 1
        afferent[edge["target"]] += 1

    coupling_scores: list[dict] = []
    for name in sorted(service_names):
        aff = afferent.get(name, 0)
        eff = efferent.get(name, 0)
        total = aff + eff
        instability = eff / total if total > 0 else 0.0
        coupling_scores.append(
            {
                "service": name,
                "afferent_coupling": aff,
                "efferent_coupling": eff,
                "instability": round(instability, 4),
            }
        )

    logger.info(
        "build_dependency_graph_complete",
        node_count=len(nodes),
        edge_count=len(edges),
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "coupling_scores": coupling_scores,
    }
