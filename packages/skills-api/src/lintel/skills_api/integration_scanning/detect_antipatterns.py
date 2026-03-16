"""Rule-based antipattern detection for service dependency graphs."""

from __future__ import annotations

from collections import defaultdict

import structlog

logger = structlog.get_logger(__name__)

# Default thresholds (can be overridden via kwargs).
_DEFAULT_EFFERENT_THRESHOLD = 5
_DEFAULT_CHATTY_EDGE_THRESHOLD = 3


async def detect_antipatterns(
    nodes: list[dict],
    edges: list[dict],
    coupling_scores: list[dict],
    *,
    efferent_threshold: int = _DEFAULT_EFFERENT_THRESHOLD,
    chatty_edge_threshold: int = _DEFAULT_CHATTY_EDGE_THRESHOLD,
    resilience_index: dict[str, dict[str, bool]] | None = None,
) -> list[dict]:
    """Detect architectural antipatterns in a service dependency graph.

    Rule-based checks:
      a. Tight coupling: service with efferent_coupling > threshold.
      b. Missing retries: HTTP edges without tenacity/retry decorator patterns.
      c. Chatty interface: >N edges between the same source-target pair.
      d. Circular dependencies: A -> B -> A cycles.

    Args:
        nodes: List of node dicts (each must have at least ``name``).
        edges: List of edge dicts (each must have ``source``, ``target``,
               and optionally ``protocol`` and ``has_retry``).
        coupling_scores: List of coupling score dicts (each must have
                         ``service``, ``efferent_coupling``).
        efferent_threshold: Efferent coupling threshold for tight-coupling
                            detection. Defaults to 5.
        chatty_edge_threshold: Edge-count threshold between the same pair
                               for chatty-interface detection. Defaults to 3.

    Returns:
        List of dicts with keys: antipattern_type, severity,
        affected_nodes, description.
    """
    findings: list[dict] = []

    # --- (a) Tight coupling --------------------------------------------------
    for score in coupling_scores:
        efferent = score.get("efferent_coupling", 0)
        if efferent > efferent_threshold:
            findings.append(
                {
                    "antipattern_type": "tight_coupling",
                    "severity": "high" if efferent > efferent_threshold * 2 else "medium",
                    "affected_nodes": [score["service"]],
                    "description": (
                        f"Service '{score['service']}' has efferent coupling of "
                        f"{efferent} (threshold: {efferent_threshold})."
                    ),
                }
            )

    # --- (b) Missing retries --------------------------------------------------
    for edge in edges:
        protocol = edge.get("protocol", "")
        has_retry = edge.get("has_retry", False)
        if protocol in ("http", "grpc") and not has_retry:
            findings.append(
                {
                    "antipattern_type": "missing_retry",
                    "severity": "medium",
                    "affected_nodes": [edge["source"], edge["target"]],
                    "description": (
                        f"HTTP/gRPC call from '{edge['source']}' to "
                        f"'{edge['target']}' has no retry/tenacity pattern."
                    ),
                }
            )

    # --- (c) Chatty interface -------------------------------------------------
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for edge in edges:
        pair_counts[(edge["source"], edge["target"])] += edge.get("call_count", 1)

    for (source, target), count in pair_counts.items():
        if count > chatty_edge_threshold:
            findings.append(
                {
                    "antipattern_type": "chatty_interface",
                    "severity": "medium",
                    "affected_nodes": [source, target],
                    "description": (
                        f"{count} edges between '{source}' and '{target}' "
                        f"(threshold: {chatty_edge_threshold}). "
                        f"Consider batching or aggregating calls."
                    ),
                }
            )

    # --- (d) Circular dependencies --------------------------------------------
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge["source"]].add(edge["target"])

    visited_cycles: set[frozenset[str]] = set()
    for node_a, targets in adjacency.items():
        for node_b in targets:
            if node_a in adjacency.get(node_b, set()):
                cycle_key = frozenset({node_a, node_b})
                if cycle_key not in visited_cycles:
                    visited_cycles.add(cycle_key)
                    findings.append(
                        {
                            "antipattern_type": "circular_dependency",
                            "severity": "high",
                            "affected_nodes": sorted([node_a, node_b]),
                            "description": (
                                f"Circular dependency detected: '{node_a}' <-> '{node_b}'."
                            ),
                        }
                    )

    logger.info("detect_antipatterns_complete", total_findings=len(findings))
    return findings
