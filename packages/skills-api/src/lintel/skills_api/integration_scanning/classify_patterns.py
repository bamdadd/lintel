"""Classify architectural patterns from a service dependency graph.

Analyzes graph topology and edge types to identify named patterns like
API Gateway, Event-Driven, Pub-Sub, CQRS, Shared Database, etc.
"""

from __future__ import annotations

from collections import defaultdict

import structlog

logger = structlog.get_logger(__name__)


def _services_by_type(
    edges: list[dict],
) -> dict[str, set[str]]:
    """Group target services by integration type."""
    result: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        itype = e.get("integration_type", "sync")
        result[itype].add(e.get("target", ""))
        result[itype].add(e.get("source", ""))
    return result


async def classify_architectural_patterns(
    nodes: list[dict],
    edges: list[dict],
    coupling_scores: list[dict],
    resilience_index: dict[str, dict[str, bool]] | None = None,
) -> list[dict]:
    """Identify named architectural patterns from graph structure.

    Returns list of dicts with keys: pattern_type, pattern_name, confidence,
    description, affected_services, details.
    """
    patterns: list[dict] = []
    if not edges:
        return patterns

    resilience_index = resilience_index or {}

    # Build adjacency structures
    out_edges: dict[str, list[dict]] = defaultdict(list)
    in_edges: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        out_edges[e["source"]].append(e)
        in_edges[e["target"]].append(e)

    service_names = {n.get("name", "") for n in nodes}

    # --- 1. API Gateway pattern -----------------------------------------------
    # A service with high fan-out to many services via sync HTTP/gRPC
    for svc in service_names:
        sync_targets = {
            e["target"]
            for e in out_edges.get(svc, [])
            if e.get("integration_type") in ("sync", "external")
        }
        sync_sources = {
            e["source"]
            for e in in_edges.get(svc, [])
            if e.get("integration_type") in ("sync", "external")
        }
        if len(sync_targets) >= 3 and len(sync_sources) <= 1:
            patterns.append(
                {
                    "pattern_type": "api_gateway",
                    "pattern_name": "API Gateway",
                    "confidence": min(0.9, 0.5 + len(sync_targets) * 0.1),
                    "description": (
                        f"'{svc}' acts as an API gateway, routing requests to "
                        f"{len(sync_targets)} downstream services."
                    ),
                    "affected_services": [svc, *sorted(sync_targets)],
                    "details": {
                        "gateway_service": svc,
                        "downstream_count": len(sync_targets),
                        "downstream_services": sorted(sync_targets),
                    },
                }
            )

    # --- 2. Event-Driven / Pub-Sub pattern ------------------------------------
    # Services communicating through async message brokers
    async_edges = [e for e in edges if e.get("integration_type") == "async"]
    if async_edges:
        broker_targets = {e["target"] for e in async_edges}
        publisher_services = {e["source"] for e in async_edges}
        all_async_services = publisher_services | broker_targets

        # Distinguish pub-sub (broker in the middle) from point-to-point
        brokers = broker_targets & {
            e["source"] for e in edges if e.get("integration_type") == "async"
        }

        if brokers:
            patterns.append(
                {
                    "pattern_type": "pub_sub",
                    "pattern_name": "Publish-Subscribe",
                    "confidence": 0.85,
                    "description": (
                        f"Event-driven architecture via message brokers: "
                        f"{', '.join(sorted(brokers))}. "
                        f"{len(publisher_services)} publishers, "
                        f"{len(broker_targets)} subscribers."
                    ),
                    "affected_services": sorted(all_async_services),
                    "details": {
                        "brokers": sorted(brokers),
                        "publishers": sorted(publisher_services),
                        "subscribers": sorted(broker_targets - brokers),
                    },
                }
            )
        elif len(async_edges) >= 2:
            patterns.append(
                {
                    "pattern_type": "event_driven",
                    "pattern_name": "Event-Driven",
                    "confidence": 0.7,
                    "description": (
                        f"{len(async_edges)} async integration(s) detected "
                        f"across {len(all_async_services)} services."
                    ),
                    "affected_services": sorted(all_async_services),
                    "details": {
                        "async_edge_count": len(async_edges),
                        "protocols": sorted({e.get("protocol", "") for e in async_edges}),
                    },
                }
            )

    # --- 3. Shared Database pattern -------------------------------------------
    # Multiple services writing to the same database target
    db_edges = [e for e in edges if e.get("integration_type") == "database"]
    db_target_sources: dict[str, set[str]] = defaultdict(set)
    for e in db_edges:
        db_target_sources[e["target"]].add(e["source"])

    for db_target, sources in db_target_sources.items():
        if len(sources) >= 2:
            patterns.append(
                {
                    "pattern_type": "shared_database",
                    "pattern_name": "Shared Database",
                    "confidence": 0.8,
                    "description": (
                        f"Database '{db_target}' is accessed by {len(sources)} services: "
                        f"{', '.join(sorted(sources))}. "
                        f"Consider if these services should own separate data stores."
                    ),
                    "affected_services": sorted(sources | {db_target}),
                    "details": {
                        "database": db_target,
                        "accessing_services": sorted(sources),
                        "service_count": len(sources),
                    },
                }
            )

    # --- 4. CQRS pattern ------------------------------------------------------
    # A service that reads from one DB and writes to another, or separate read/write paths
    for svc in service_names:
        svc_db_targets = [
            e for e in out_edges.get(svc, []) if e.get("integration_type") == "database"
        ]
        if len(svc_db_targets) >= 2:
            db_names = {e["target"] for e in svc_db_targets}
            if len(db_names) >= 2:
                patterns.append(
                    {
                        "pattern_type": "cqrs",
                        "pattern_name": "CQRS (Command Query Separation)",
                        "confidence": 0.6,
                        "description": (
                            f"'{svc}' connects to multiple databases "
                            f"({', '.join(sorted(db_names))}), suggesting "
                            f"separate read and write data stores."
                        ),
                        "affected_services": [svc, *sorted(db_names)],
                        "details": {
                            "service": svc,
                            "databases": sorted(db_names),
                        },
                    }
                )

    # --- 5. Saga / Choreography pattern ---------------------------------------
    # Chain of async edges: A → broker → B → broker → C
    async_chains: list[list[str]] = []
    visited: set[str] = set()
    for svc in service_names:
        if svc in visited:
            continue
        chain = [svc]
        current = svc
        while True:
            async_targets = [
                e["target"]
                for e in out_edges.get(current, [])
                if e.get("integration_type") == "async" and e["target"] not in visited
            ]
            if not async_targets:
                break
            nxt = async_targets[0]
            chain.append(nxt)
            visited.add(nxt)
            current = nxt
        if len(chain) >= 3:
            async_chains.append(chain)

    for chain in async_chains:
        patterns.append(
            {
                "pattern_type": "saga_choreography",
                "pattern_name": "Saga / Choreography",
                "confidence": 0.55 + min(0.3, len(chain) * 0.05),
                "description": (
                    f"Async processing chain spanning {len(chain)} services: {' → '.join(chain)}."
                ),
                "affected_services": chain,
                "details": {
                    "chain_length": len(chain),
                    "chain": chain,
                },
            }
        )

    # --- 6. Backend-for-Frontend (BFF) ----------------------------------------
    # A service with both incoming sync and outgoing sync + DB edges
    for svc in service_names:
        has_sync_in = any(
            e.get("integration_type") in ("sync", "external") for e in in_edges.get(svc, [])
        )
        sync_out = [
            e for e in out_edges.get(svc, []) if e.get("integration_type") in ("sync", "database")
        ]
        if has_sync_in and len(sync_out) >= 2:
            out_types = {e.get("integration_type") for e in sync_out}
            if "database" in out_types and "sync" in out_types:
                patterns.append(
                    {
                        "pattern_type": "backend_for_frontend",
                        "pattern_name": "Backend-for-Frontend (BFF)",
                        "confidence": 0.5,
                        "description": (
                            f"'{svc}' aggregates data from multiple sources "
                            f"(APIs + databases) for upstream consumers."
                        ),
                        "affected_services": [svc],
                        "details": {
                            "service": svc,
                            "outgoing_types": sorted(out_types),
                        },
                    }
                )

    # --- 7. External Integration Layer ----------------------------------------
    # Services calling external APIs
    ext_edges = [e for e in edges if e.get("integration_type") == "external"]
    if ext_edges:
        ext_services = {e["source"] for e in ext_edges}
        ext_targets = {e["target"] for e in ext_edges}

        # Check resilience posture
        resilient_count = 0
        for e in ext_edges:
            sf = e.get("source_file", "")
            ri = resilience_index.get(sf, {})
            if ri.get("has_retry") or ri.get("has_circuit_breaker"):
                resilient_count += 1

        resilience_ratio = resilient_count / len(ext_edges) if ext_edges else 0

        patterns.append(
            {
                "pattern_type": "external_integration",
                "pattern_name": "External API Integration",
                "confidence": 0.9,
                "description": (
                    f"{len(ext_services)} service(s) integrate with "
                    f"{len(ext_targets)} external APIs. "
                    f"Resilience coverage: {resilience_ratio:.0%}."
                ),
                "affected_services": sorted(ext_services | ext_targets),
                "details": {
                    "integrating_services": sorted(ext_services),
                    "external_apis": sorted(ext_targets),
                    "resilience_coverage": round(resilience_ratio, 2),
                    "total_external_edges": len(ext_edges),
                },
            }
        )

    # --- 8. Request-Reply pattern ---------------------------------------------
    # Bidirectional sync edges between two services
    sync_pairs: set[frozenset[str]] = set()
    for e in edges:
        if e.get("integration_type") != "sync":
            continue
        reverse = any(
            r["source"] == e["target"]
            and r["target"] == e["source"]
            and r.get("integration_type") == "sync"
            for r in edges
        )
        if reverse:
            pair = frozenset({e["source"], e["target"]})
            sync_pairs.add(pair)

    for pair in sync_pairs:
        svcs = sorted(pair)
        patterns.append(
            {
                "pattern_type": "request_reply",
                "pattern_name": "Request-Reply",
                "confidence": 0.75,
                "description": (
                    f"Bidirectional sync communication between '{svcs[0]}' and '{svcs[1]}'."
                ),
                "affected_services": svcs,
                "details": {"services": svcs},
            }
        )

    logger.info("classify_architectural_patterns_complete", pattern_count=len(patterns))
    return patterns
