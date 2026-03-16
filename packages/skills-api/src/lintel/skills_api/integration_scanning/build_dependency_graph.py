"""Build a service dependency graph from aggregated scan results."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

import structlog

logger = structlog.get_logger(__name__)

# Directories that should never be treated as service names.
_EXCLUDED_DIRS: frozenset[str] = frozenset({
    "tests",
    "test",
    "testing",
    "__pycache__",
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "docs",
    "scripts",
    "migrations",
    "fixtures",
    "conftest",
    "examples",
    "benchmarks",
})

# Map scanner key → (integration_type, default_protocol)
_SCANNER_TYPE_MAP: dict[str, tuple[str, str]] = {
    "sync_integrations": ("sync", "http"),
    "async_integrations": ("async", "amqp"),
    "db_integrations": ("database", "sql"),
    "file_blob_integrations": ("file", "filesystem"),
    "external_api_calls": ("external", "https"),
}


def _infer_service_name(file_path: str) -> str | None:
    """Infer a service name from a file path using a directory heuristic.

    Returns None if the path resolves to an excluded directory (tests, etc.).
    """
    parts = PurePosixPath(file_path).parts
    # Walk up from the parent dir, skipping excluded dirs
    for i in range(len(parts) - 2, -1, -1):
        candidate = parts[i]
        if candidate.lower() not in _EXCLUDED_DIRS and not candidate.startswith("."):
            return candidate
    # Last resort: file stem (skip test files)
    stem = PurePosixPath(file_path).stem
    lower_stem = stem.lower()
    if lower_stem not in _EXCLUDED_DIRS and not lower_stem.startswith("test_"):
        return stem
    return None


def _extract_target(result: dict) -> str | None:
    """Extract the target service / system name from a single scan result."""
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


def _extract_protocol(result: dict, default: str) -> str:
    """Extract the protocol from a scan result with a scanner-specific default."""
    return str(result.get("protocol", default))


async def build_dependency_graph(scan_results: dict) -> dict:
    """Build a dependency graph from aggregated scan results.

    Args:
        scan_results: Dict whose keys are scanner names and values are
            the lists returned by the corresponding scanner function.

    Returns:
        Dict with three top-level keys:
          - nodes: list of ``{name: str}``
          - edges: list of ``{source, target, protocol, integration_type, ...}``
          - coupling_scores: list of ``{service, afferent_coupling,
            efferent_coupling, instability}``
    """
    # ---- Build edges ---------------------------------------------------------
    edges: list[dict] = []
    service_names: set[str] = set()

    for scanner_name, results in scan_results.items():
        if not isinstance(results, list):
            continue

        integration_type, default_protocol = _SCANNER_TYPE_MAP.get(
            scanner_name, ("sync", "unknown"),
        )

        for result in results:
            source_file = result.get("source_file", "")
            source_service = _infer_service_name(source_file)
            if source_service is None:
                continue

            target = _extract_target(result)
            if target is None:
                continue

            service_names.add(source_service)
            service_names.add(target)

            edges.append(
                {
                    "source": source_service,
                    "target": target,
                    "protocol": _extract_protocol(result, default_protocol),
                    "integration_type": integration_type,
                    "source_file": source_file,
                    "line_number": result.get("line_number", 0),
                    "has_retry": result.get("has_retry", False),
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
