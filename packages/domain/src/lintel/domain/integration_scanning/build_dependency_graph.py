"""Build a service dependency graph from aggregated scan results."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

import structlog

logger = structlog.get_logger(__name__)

# Directories that should never be treated as service names.
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
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
    }
)

# Map scanner key → (integration_type, default_protocol)
_SCANNER_TYPE_MAP: dict[str, tuple[str, str]] = {
    "sync_integrations": ("sync", "http"),
    "async_integrations": ("async", "amqp"),
    "db_integrations": ("database", "sql"),
    "file_blob_integrations": ("file", "filesystem"),
    "external_api_calls": ("external", "https"),
}

# Edge weight by integration type — reflects criticality & failure impact.
_TYPE_WEIGHTS: dict[str, float] = {
    "external": 3.0,
    "database": 2.5,
    "sync": 2.0,
    "async": 1.0,
    "file": 0.5,
}

# Resilience discount factors.
_RESILIENCE_DISCOUNTS: dict[str, float] = {
    "has_retry": 0.15,
    "has_circuit_breaker": 0.25,
    "has_timeout": 0.10,
    "has_bulkhead": 0.10,
}

# ---- Target normalisation ----------------------------------------------------
# Map raw library/SDK names to canonical category names and node_type.
# (canonical_name, node_type)
_TARGET_CATEGORY: dict[str, tuple[str, str]] = {
    # HTTP client libraries → NOT a service node; the edge target should be
    # the source service's generic "HTTP" dependency.  We map these to None
    # in the code below to suppress creating a target node.
    "requests": ("HTTP Client", "library"),
    "httpx": ("HTTP Client", "library"),
    "aiohttp": ("HTTP Client", "library"),
    "grpc": ("gRPC", "library"),
    "graphql-core": ("GraphQL", "library"),
    "graphql-client": ("GraphQL", "library"),
    "websocket": ("WebSocket", "library"),
    # Databases
    "sqlalchemy": ("PostgreSQL", "database"),
    "asyncpg": ("PostgreSQL", "database"),
    "mongodb": ("MongoDB", "database"),
    "redis": ("Redis", "database"),
    "redis_pubsub": ("Redis", "message_broker"),
    "elasticsearch": ("Elasticsearch", "database"),
    "mysql": ("MySQL", "database"),
    "sqlite": ("SQLite", "database"),
    "dynamodb": ("DynamoDB", "database"),
    # Message brokers
    "kafka": ("Kafka", "message_broker"),
    "aiokafka": ("Kafka", "message_broker"),
    "nats": ("NATS", "message_broker"),
    "rabbitmq": ("RabbitMQ", "message_broker"),
    # Cloud storage
    "s3": ("AWS S3", "external_api"),
    "azure_blob": ("Azure Blob Storage", "external_api"),
    "gcs": ("Google Cloud Storage", "external_api"),
    "local_file": ("Local Filesystem", "file_system"),
    # External APIs / SDKs
    "stripe": ("Stripe", "external_api"),
    "twilio": ("Twilio", "external_api"),
    "sendgrid": ("SendGrid", "external_api"),
    "slack": ("Slack API", "external_api"),
    "aws_sdk": ("AWS SDK", "external_api"),
    "gcp_sdk": ("Google Cloud", "external_api"),
    "azure_sdk": ("Azure SDK", "external_api"),
    "openai": ("OpenAI", "external_api"),
    "anthropic": ("Anthropic", "external_api"),
    "pagerduty": ("PagerDuty", "external_api"),
    "datadog": ("Datadog", "external_api"),
    "sentry": ("Sentry", "external_api"),
    "openapi_generated": ("OpenAPI Client", "external_api"),
    "external_http": ("External HTTP", "external_api"),
}

# Library targets that should NOT create standalone service nodes.
# Edges to these become outgoing properties of the source service instead.
_LIBRARY_TARGETS: frozenset[str] = frozenset(
    name for name, (_, ntype) in _TARGET_CATEGORY.items() if ntype == "library"
)


def _normalise_target(raw_target: str) -> tuple[str, str]:
    """Map a raw target name to (canonical_name, node_type).

    Falls back to treating the target as a service.
    """
    if raw_target in _TARGET_CATEGORY:
        return _TARGET_CATEGORY[raw_target]
    return (raw_target, "service")


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


async def build_dependency_graph(
    scan_results: dict,
    resilience_index: dict[str, dict[str, bool]] | None = None,
) -> dict:
    """Build a dependency graph from aggregated scan results.

    Args:
        scan_results: Dict whose keys are scanner names and values are
            the lists returned by the corresponding scanner function.
        resilience_index: Optional per-file resilience capabilities.

    Returns:
        Dict with three top-level keys:
          - nodes: list of ``{name, node_type}``
          - edges: list of ``{source, target, protocol, integration_type, ...}``
          - coupling_scores: list of weighted coupling metrics
    """
    resilience_index = resilience_index or {}

    # ---- Build raw edges -----------------------------------------------------
    raw_edges: list[dict] = []
    node_types: dict[str, str] = {}  # name → node_type

    for scanner_name, results in scan_results.items():
        if not isinstance(results, list):
            continue
        # Skip resilience scanner results (they enrich, not produce edges)
        if scanner_name == "resilience_patterns":
            continue

        integration_type, default_protocol = _SCANNER_TYPE_MAP.get(
            scanner_name,
            ("sync", "unknown"),
        )

        for result in results:
            source_file = result.get("source_file", "")
            source_service = _infer_service_name(source_file)
            if source_service is None:
                continue

            raw_target = _extract_target(result)
            if raw_target is None:
                continue

            # Normalise target name and determine node types
            target_name, target_node_type = _normalise_target(raw_target)

            # For library targets (requests, httpx), skip creating a separate
            # node. The edge still exists for analysis but the target is the
            # canonical category name (e.g. "HTTP Client").
            if raw_target in _LIBRARY_TARGETS:
                # Don't create edges to pure library targets — they add noise.
                # The source service's integration_type captures this.
                continue

            # Track node types
            if source_service not in node_types:
                node_types[source_service] = "service"
            node_types[target_name] = target_node_type

            # Merge resilience info from file-level index
            file_resilience = resilience_index.get(source_file, {})

            raw_edges.append(
                {
                    "source": source_service,
                    "target": target_name,
                    "protocol": _extract_protocol(result, default_protocol),
                    "integration_type": integration_type,
                    "source_file": source_file,
                    "line_number": result.get("line_number", 0),
                    "has_retry": file_resilience.get("has_retry", False),
                    "has_circuit_breaker": file_resilience.get("has_circuit_breaker", False),
                    "has_timeout": (
                        file_resilience.get("has_timeout", False)
                        or result.get("has_timeout", False)
                    ),
                    "has_connection_pool": result.get("has_connection_pool", False),
                    "url_host": result.get("url_host"),
                }
            )

    # ---- Deduplicate edges at service level ----------------------------------
    # Collapse (source, target, integration_type) into single edges with counts
    edge_key_map: dict[tuple[str, str, str], dict] = {}
    for e in raw_edges:
        key = (e["source"], e["target"], e["integration_type"])
        if key in edge_key_map:
            existing = edge_key_map[key]
            existing["call_count"] += 1
            # Merge resilience (any file having it counts)
            for rk in ("has_retry", "has_circuit_breaker", "has_timeout"):
                if e.get(rk):
                    existing[rk] = True
            if e.get("has_connection_pool"):
                existing["has_connection_pool"] = True
            # Collect unique protocols
            existing.setdefault("_protocols", set()).add(e["protocol"])
        else:
            entry = dict(e)
            entry["call_count"] = 1
            entry["_protocols"] = {e["protocol"]}
            edge_key_map[key] = entry

    edges: list[dict] = []
    for entry in edge_key_map.values():
        protocols = entry.pop("_protocols", set())
        if len(protocols) > 1:
            entry["protocol"] = ", ".join(sorted(protocols))
        edges.append(entry)

    # ---- Build nodes ---------------------------------------------------------
    all_names = {e["source"] for e in edges} | {e["target"] for e in edges}
    nodes: list[dict] = [
        {"name": name, "node_type": node_types.get(name, "service")} for name in sorted(all_names)
    ]

    # ---- Compute weighted coupling scores ------------------------------------
    coupling_scores = _compute_weighted_coupling(nodes, edges, resilience_index)

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


def _compute_weighted_coupling(
    nodes: list[dict],
    edges: list[dict],
    resilience_index: dict[str, dict[str, bool]],
) -> list[dict]:
    """Compute weighted coupling scores using edge type weights and resilience."""
    raw_afferent: dict[str, int] = defaultdict(int)
    raw_efferent: dict[str, int] = defaultdict(int)
    w_afferent: dict[str, float] = defaultdict(float)
    w_efferent: dict[str, float] = defaultdict(float)
    svc_resilience: dict[str, list[dict[str, bool]]] = defaultdict(list)

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        itype = edge.get("integration_type", "sync")
        call_count = edge.get("call_count", 1)
        base_weight = _TYPE_WEIGHTS.get(itype, 1.0)

        discount = sum(
            disc for res_key, disc in _RESILIENCE_DISCOUNTS.items() if edge.get(res_key, False)
        )
        effective_weight = base_weight * max(0.3, 1.0 - discount)

        raw_efferent[src] += 1
        raw_afferent[tgt] += 1
        w_efferent[src] += effective_weight * min(call_count, 3)  # Cap at 3x
        w_afferent[tgt] += effective_weight * min(call_count, 3)

        svc_resilience[src].append(
            {
                "has_retry": edge.get("has_retry", False),
                "has_circuit_breaker": edge.get("has_circuit_breaker", False),
                "has_timeout": edge.get("has_timeout", False),
            }
        )

    service_names = {n.get("name", "") for n in nodes}
    coupling_scores: list[dict] = []

    for name in sorted(service_names):
        ra = raw_afferent.get(name, 0)
        re_ = raw_efferent.get(name, 0)
        wa = round(w_afferent.get(name, 0.0), 2)
        we = round(w_efferent.get(name, 0.0), 2)
        total = ra + re_
        w_total = wa + we

        instability = re_ / total if total > 0 else 0.0
        w_instability = we / w_total if w_total > 0 else 0.0

        edges_out = svc_resilience.get(name, [])
        if edges_out:
            resilience_score = sum(
                1 for e in edges_out if e.get("has_retry") or e.get("has_circuit_breaker")
            ) / len(edges_out)
        else:
            resilience_score = 1.0

        coupling_scores.append(
            {
                "service": name,
                "afferent_coupling": ra,
                "efferent_coupling": re_,
                "weighted_afferent": wa,
                "weighted_efferent": we,
                "instability": round(instability, 4),
                "weighted_instability": round(w_instability, 4),
                "resilience_score": round(resilience_score, 4),
            }
        )

    return coupling_scores
