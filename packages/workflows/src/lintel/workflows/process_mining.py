"""Process-mining workflow graph using LangGraph.

Scans a repository to discover data/process flows: HTTP request paths,
event sourcing chains, command dispatch routes, background jobs, and
external integrations.  Produces individual Mermaid diagrams per flow type.
"""

from __future__ import annotations

import os
import re
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class ProcessMiningState(TypedDict):
    """State for the process-mining workflow graph."""

    # Common ingest / setup fields
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

    # Process-mining specific
    repository_id: str
    flow_map_id: str
    discovered_endpoints: list[dict[str, Any]]
    traced_flows: list[dict[str, Any]]
    classified_flows: dict[str, list[dict[str, Any]]]
    diagrams: list[dict[str, Any]]
    metrics: dict[str, Any]
    errors: list[str]
    status: str


# ---------------------------------------------------------------------------
# Endpoint discovery helpers
# ---------------------------------------------------------------------------

# Regex patterns for each endpoint type
_ROUTE_PATTERNS = [
    # FastAPI / Flask / Starlette
    (r"@\w*(?:router|app)\.\s*(?:get|post|put|patch|delete|head|options)\s*\(", "http_route"),
    # Event handler subscriptions
    (r"(?:event_bus|bus)\.subscribe\s*\(", "event_handler"),
    (r"@event_handler", "event_handler"),
    # Command dispatcher
    (r"dispatcher\.register\s*\(", "command_handler"),
    (r"@command_handler", "command_handler"),
    # Background / cron
    (r"@(?:celery_app|app)\.task", "background_job"),
    (r"(?:scheduler|cron|APScheduler).*(?:add_job|scheduled_job|crontab)", "background_job"),
    (r"asyncio\.create_task\s*\(", "async_task"),
    # Message queue consumers
    (r"(?:kafka|nats|rabbit|amqp).*(?:subscribe|consume|listen)", "mq_consumer"),
]


def _scan_file_for_endpoints(
    content: str,
    file_path: str,
) -> list[dict[str, Any]]:
    """Scan a single file for endpoint/handler registrations."""
    import re

    results: list[dict[str, Any]] = []
    lines = content.splitlines()
    for line_no, line in enumerate(lines, start=1):
        for pattern, ep_type in _ROUTE_PATTERNS:
            if re.search(pattern, line):
                # Try to extract function name from the next non-decorator line
                func_name = _extract_func_name(lines, line_no - 1)
                results.append(
                    {
                        "file_path": file_path,
                        "line_number": line_no,
                        "endpoint_type": ep_type,
                        "function_name": func_name,
                        "raw_line": line.strip()[:200],
                    }
                )
    return results


def _extract_func_name(lines: list[str], start_idx: int) -> str:
    """Walk forward from a decorator to find the function name."""
    import re

    for i in range(start_idx, min(start_idx + 5, len(lines))):
        m = re.match(r"\s*(?:async\s+)?def\s+(\w+)", lines[i])
        if m:
            return m.group(1)
    return "<unknown>"


# ---------------------------------------------------------------------------
# Flow tracing helpers
# ---------------------------------------------------------------------------


def _trace_call_chain(
    content: str,
    func_name: str,
    file_path: str,
    all_files: dict[str, str],
    *,
    max_depth: int = 8,
) -> list[dict[str, Any]]:
    """Lightweight AST-free call chain tracer.

    Follows function calls within a function body to build a chain of steps.
    """
    import re

    steps: list[dict[str, Any]] = []
    lines = content.splitlines()

    # Find the function body
    in_func = False
    indent = 0
    for line_no, line in enumerate(lines, start=1):
        if re.match(rf"\s*(?:async\s+)?def\s+{re.escape(func_name)}\s*\(", line):
            in_func = True
            indent = len(line) - len(line.lstrip())
            continue
        if in_func:
            if line.strip() and not line.strip().startswith("#"):
                cur_indent = len(line) - len(line.lstrip())
                if cur_indent <= indent and line.strip():
                    break
                step_type = _classify_line(line)
                if step_type:
                    steps.append(
                        {
                            "file_path": file_path,
                            "function_name": func_name,
                            "line_number": line_no,
                            "step_type": step_type,
                            "description": line.strip()[:120],
                        }
                    )
            if len(steps) >= max_depth:
                break

    return steps


def _classify_line(line: str) -> str | None:
    """Classify a line of code by its role in the data flow."""
    stripped = line.strip()
    if any(kw in stripped for kw in ("await store.", "await self._pool", ".execute(", ".fetch")):
        return "store"
    if any(kw in stripped for kw in ("dispatch_event", "event_bus.publish", "event_store.append")):
        return "event_bus"
    if any(kw in stripped for kw in ("await projection", "project(event")):
        return "projection"
    if any(kw in stripped for kw in ("httpx.", "aiohttp.", "requests.", "AsyncClient")):
        return "external_api"
    if any(kw in stripped for kw in (".send_message", "post_message", "chat_postMessage")):
        return "external_api"
    if any(kw in stripped for kw in ("Depends(", "StoreProvider", "@inject")):
        return "middleware"
    if any(kw in stripped for kw in ("conn.execute", "conn.fetch", "INSERT INTO", "SELECT ")):
        return "database"
    return None


# ---------------------------------------------------------------------------
# Diagram generation helpers
# ---------------------------------------------------------------------------


def _generate_mermaid_diagram(
    flow_type: str,
    flows: list[dict[str, Any]],
) -> str:
    """Generate a Mermaid sequence diagram for a group of flows."""
    if not flows:
        return ""

    title_map = {
        "http_request": "HTTP Request Flow",
        "event_sourcing": "Event Sourcing Flow",
        "command_dispatch": "Command Dispatch Flow",
        "background_job": "Background Job Flow",
        "external_integration": "External Integration Flow",
    }
    title = title_map.get(flow_type, flow_type.replace("_", " ").title())

    lines = ["sequenceDiagram"]

    # Collect unique role-based participants in order
    participants: list[str] = []
    for flow in flows[:10]:
        source = flow.get("source", {})
        sink = flow.get("sink") or {}
        for step in [source, *flow.get("steps", []), sink]:
            if not step:
                continue
            name = _participant_name(step)
            if name and name not in participants:
                participants.append(name)

    for p in participants:
        lines.append(f"    participant {p}")

    lines.append(f"    Note over {participants[0] if participants else 'Client'}: {title}")

    for flow in flows[:10]:
        source = flow.get("source", {})
        steps = flow.get("steps", [])
        sink = flow.get("sink") or {}
        flow_name = flow.get("name", "flow")

        all_steps = [s for s in [source, *steps, sink] if s]
        if len(all_steps) < 2:
            continue

        # Build arrows between consecutive role-based participants
        prev_role = _participant_name(all_steps[0])
        for step in all_steps[1:]:
            cur_role = _participant_name(step)
            if not cur_role or cur_role == prev_role:
                continue
            fn = step.get("function_name", "")
            desc = step.get("description", "")
            # Pick the best label: function name or truncated description
            label = (
                fn
                if fn and fn != "<unknown>" and "<" not in fn
                else desc[:40]
                if desc
                else step.get("step_type", "")
            )
            # Sanitise label for Mermaid (no angle brackets, no colons)
            label = re.sub(r"[<>:]", "", label).strip() or "call"
            lines.append(f"    {prev_role}->>{cur_role}: {label}")
            prev_role = cur_role

    return "\n".join(lines)


def _participant_name(step: dict[str, Any]) -> str:
    """Derive a role-based participant name from a flow step."""
    st = step.get("step_type", "")
    role_map = {
        "database": "DB",
        "store": "Store",
        "event_bus": "EventBus",
        "projection": "Projection",
        "external_api": "ExternalAPI",
        "middleware": "Middleware",
        "entrypoint": "Router",
        "handler": "Handler",
        "service": "Service",
        "message_queue": "MessageQueue",
        "scheduler": "Scheduler",
    }
    name = role_map.get(st, "")
    if not name:
        # Sanitise: remove angle brackets, spaces, and other Mermaid-invalid chars
        name = re.sub(r"[<>\s/\\(){}]", "", st.replace("_", "").title())[:15]
    return name or "Component"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def discover_endpoints_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Scan repository files for HTTP routes, event handlers, command handlers, cron jobs."""
    import tempfile

    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("discover_endpoints")

    workspace_path = state.get("workspace_path") or state.get("repo_path", "")
    sandbox_id = state.get("sandbox_id") or ""
    errors: list[str] = []

    _configurable = config.get("configurable", {})
    sandbox_manager = _configurable.get("sandbox_manager")
    if sandbox_manager is None:
        app_state = _configurable.get("app_state")
        if app_state is not None:
            sandbox_manager = getattr(app_state, "sandbox_manager", None)

    if not sandbox_manager or not sandbox_id:
        errors.append("No sandbox available for scanning")
        await tracker.mark_completed("discover_endpoints", error="No sandbox available")
        return {"discovered_endpoints": [], "errors": errors, "status": "failed"}

    # List source files
    try:
        find_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"find {workspace_path} -name '*.py' -o -name '*.ts' -o -name '*.go' "
                    f"-o -name '*.java' | grep -v __pycache__ | grep -v node_modules | grep -v .venv"
                ),
                workdir="/",
                timeout_seconds=30,
            ),
        )
        remote_files = [f for f in find_result.stdout.strip().splitlines() if f]
    except Exception as exc:
        errors.append(f"File listing failed: {exc}")
        await tracker.mark_completed("discover_endpoints", error=str(exc))
        return {"discovered_endpoints": [], "errors": errors, "status": "failed"}

    if not remote_files:
        await tracker.append_log("discover_endpoints", "No source files found.")
        await tracker.mark_completed("discover_endpoints")
        return {"discovered_endpoints": [], "errors": errors, "status": "completed"}

    await tracker.append_log("discover_endpoints", f"Found {len(remote_files)} source files.")

    # Download via tar
    local_tmpdir = tempfile.mkdtemp(prefix="lintel_pm_")
    local_files: list[str] = []
    try:
        tar_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(f"tar cf - -C / {' '.join(f.lstrip('/') for f in remote_files[:2000])}"),
                workdir="/",
                timeout_seconds=60,
            ),
        )
        import subprocess

        proc = subprocess.run(
            ["tar", "xf", "-", "-C", local_tmpdir],
            input=(
                tar_result.stdout.encode()
                if isinstance(tar_result.stdout, str)
                else tar_result.stdout
            ),
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"tar extract failed: {proc.stderr[:200]}")

        for root, _dirs, files in os.walk(local_tmpdir):
            for fname in files:
                local_files.append(os.path.join(root, fname))
    except Exception as exc:
        errors.append(f"File download failed: {exc}")
        await tracker.mark_completed("discover_endpoints", error=str(exc))
        return {"discovered_endpoints": [], "errors": errors, "status": "failed"}

    # Scan each file
    all_endpoints: list[dict[str, Any]] = []
    for local_path in local_files:
        try:
            with open(local_path) as fh:
                content = fh.read()
        except Exception:
            continue
        rel_path = os.path.relpath(local_path, local_tmpdir)
        all_endpoints.extend(_scan_file_for_endpoints(content, rel_path))

    await tracker.append_log(
        "discover_endpoints",
        f"Discovered {len(all_endpoints)} endpoints/handlers.",
    )
    await tracker.mark_completed(
        "discover_endpoints",
        outputs={"endpoint_count": len(all_endpoints)},
    )

    return {"discovered_endpoints": all_endpoints, "errors": errors, "status": "completed"}


async def trace_flows_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """For each discovered endpoint, trace the data flow through the codebase."""
    import tempfile

    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("trace_flows")

    endpoints = state.get("discovered_endpoints", [])
    if not endpoints:
        await tracker.append_log("trace_flows", "No endpoints to trace.")
        await tracker.mark_completed("trace_flows")
        return {"traced_flows": []}

    # Read all files into memory for tracing
    _configurable = config.get("configurable", {})
    sandbox_manager = _configurable.get("sandbox_manager")
    if sandbox_manager is None:
        app_state = _configurable.get("app_state")
        if app_state is not None:
            sandbox_manager = getattr(app_state, "sandbox_manager", None)

    workspace_path = state.get("workspace_path") or ""
    sandbox_id = state.get("sandbox_id") or ""

    # Group endpoints by file to minimise reads
    files_needed: set[str] = {ep["file_path"] for ep in endpoints}
    file_contents: dict[str, str] = {}

    if sandbox_manager and sandbox_id:
        local_tmpdir = tempfile.mkdtemp(prefix="lintel_pm_trace_")
        try:
            from lintel.sandbox.types import SandboxJob

            tar_paths = " ".join(f.lstrip("/") for f in files_needed)
            tar_result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=f"tar cf - -C / {tar_paths}",
                    workdir="/",
                    timeout_seconds=60,
                ),
            )
            import subprocess

            subprocess.run(
                ["tar", "xf", "-", "-C", local_tmpdir],
                input=(
                    tar_result.stdout.encode()
                    if isinstance(tar_result.stdout, str)
                    else tar_result.stdout
                ),
                capture_output=True,
                timeout=30,
            )
            for root, _dirs, files in os.walk(local_tmpdir):
                for fname in files:
                    local_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(local_path, local_tmpdir)
                    try:
                        with open(local_path) as fh:
                            file_contents[rel_path] = fh.read()
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("trace_flows_file_read_failed", error=str(exc))

    # Trace each endpoint
    from uuid import uuid4

    flow_map_id = state.get("flow_map_id", "")
    traced: list[dict[str, Any]] = []

    for ep in endpoints:
        fp = ep["file_path"]
        content = file_contents.get(fp, "")
        if not content:
            continue

        func = ep.get("function_name", "")
        steps = _trace_call_chain(content, func, fp, file_contents)

        source_step = {
            "file_path": fp,
            "function_name": func,
            "line_number": ep.get("line_number", 0),
            "step_type": "entrypoint",
            "description": ep.get("raw_line", "")[:120],
        }

        sink_step = steps[-1] if steps else None

        traced.append(
            {
                "flow_id": str(uuid4()),
                "flow_map_id": flow_map_id,
                "flow_type": "",  # classified later
                "name": f"{ep.get('endpoint_type', '')}:{func}",
                "source": source_step,
                "steps": steps,
                "sink": sink_step,
                "metadata": {"endpoint_type": ep.get("endpoint_type", "")},
            }
        )

    await tracker.append_log("trace_flows", f"Traced {len(traced)} flows.")
    await tracker.mark_completed("trace_flows", outputs={"flow_count": len(traced)})

    return {"traced_flows": traced}


async def classify_flows_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Categorise each traced flow by FlowType."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("classify_flows")

    flows = state.get("traced_flows", [])
    classified: dict[str, list[dict[str, Any]]] = {}

    _EP_TO_FLOW = {
        "http_route": "http_request",
        "event_handler": "event_sourcing",
        "command_handler": "command_dispatch",
        "background_job": "background_job",
        "async_task": "background_job",
        "mq_consumer": "event_sourcing",
    }

    for flow in flows:
        ep_type = flow.get("metadata", {}).get("endpoint_type", "")
        flow_type = _EP_TO_FLOW.get(ep_type, "external_integration")

        # Refine based on sink type
        sink = flow.get("sink") or {}
        if sink.get("step_type") == "external_api":
            flow_type = "external_integration"
        elif sink.get("step_type") == "event_bus":
            flow_type = "event_sourcing"

        flow["flow_type"] = flow_type
        classified.setdefault(flow_type, []).append(flow)

    summary = {k: len(v) for k, v in classified.items()}
    await tracker.append_log("classify_flows", f"Classified flows: {summary}")
    await tracker.mark_completed("classify_flows", outputs=summary)

    return {"traced_flows": flows, "classified_flows": classified}


async def generate_diagrams_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Generate individual Mermaid diagrams per flow type."""
    from uuid import uuid4

    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("generate_diagrams")

    classified = state.get("classified_flows", {})
    flow_map_id = state.get("flow_map_id", "")
    diagrams: list[dict[str, Any]] = []

    for flow_type, flows in classified.items():
        mermaid = _generate_mermaid_diagram(flow_type, flows)
        if mermaid:
            diagrams.append(
                {
                    "diagram_id": str(uuid4()),
                    "flow_map_id": flow_map_id,
                    "flow_type": flow_type,
                    "title": flow_type.replace("_", " ").title(),
                    "mermaid_source": mermaid,
                    "flow_ids": tuple(f["flow_id"] for f in flows),
                }
            )

    # Compute metrics
    all_flows = state.get("traced_flows", [])
    depths = [len(f.get("steps", [])) for f in all_flows]
    metrics = {
        "metrics_id": str(uuid4()),
        "flow_map_id": flow_map_id,
        "total_flows": len(all_flows),
        "flows_by_type": {k: len(v) for k, v in classified.items()},
        "avg_depth": sum(depths) / len(depths) if depths else 0.0,
        "max_depth": max(depths) if depths else 0,
        "complexity_score": len(all_flows) * (max(depths) if depths else 0) / 100.0,
    }

    await tracker.append_log(
        "generate_diagrams",
        f"Generated {len(diagrams)} diagrams, {len(all_flows)} total flows.",
    )
    await tracker.mark_completed(
        "generate_diagrams",
        outputs={"diagram_count": len(diagrams)},
    )

    return {"diagrams": diagrams, "metrics": metrics}


async def persist_results_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Save flow maps, flows, diagrams, and metrics to the store."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from lintel.process_mining_api.types import (
        FlowDiagram,
        FlowEntry,
        FlowMetrics,
        FlowStep,
        ProcessFlowMap,
    )
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    await tracker.mark_running("persist_results")

    _configurable = config.get("configurable", {})
    app_state = _configurable.get("app_state")
    store = getattr(app_state, "process_mining_store", None) if app_state else None

    if store is None:
        logger.warning("persist_results_no_store")
        await tracker.mark_completed("persist_results", error="No process mining store")
        return {"status": "completed"}

    flow_map_id = state.get("flow_map_id") or str(uuid4())
    now = datetime.now(tz=UTC).isoformat()

    # Create flow map
    flow_map = ProcessFlowMap(
        flow_map_id=flow_map_id,
        repository_id=state.get("repository_id", ""),
        workflow_run_id=state.get("run_id", ""),
        status="completed",
        created_at=now,
        updated_at=now,
    )
    await store.create_map(flow_map)

    # Persist flows
    traced = state.get("traced_flows", [])
    flow_entries: list[FlowEntry] = []
    for f in traced:
        source = f.get("source", {})
        sink = f.get("sink")
        steps_raw = f.get("steps", [])
        flow_entries.append(
            FlowEntry(
                flow_id=f.get("flow_id", str(uuid4())),
                flow_map_id=flow_map_id,
                flow_type=f.get("flow_type", ""),
                name=f.get("name", ""),
                source=FlowStep(**source) if isinstance(source, dict) else source,
                steps=tuple(FlowStep(**s) if isinstance(s, dict) else s for s in steps_raw),
                sink=FlowStep(**sink) if isinstance(sink, dict) and sink else None,
            )
        )
    if flow_entries:
        await store.add_flows(flow_entries)

    # Persist diagrams
    diagrams_raw = state.get("diagrams", [])
    diagram_entries: list[FlowDiagram] = []
    for d in diagrams_raw:
        fids = d.get("flow_ids", ())
        diagram_entries.append(
            FlowDiagram(
                diagram_id=d.get("diagram_id", str(uuid4())),
                flow_map_id=flow_map_id,
                flow_type=d.get("flow_type", ""),
                title=d.get("title", ""),
                mermaid_source=d.get("mermaid_source", ""),
                flow_ids=tuple(fids) if isinstance(fids, (list, tuple)) else (),
            )
        )
    if diagram_entries:
        await store.add_diagrams(diagram_entries)

    # Persist metrics
    metrics_raw = state.get("metrics")
    if metrics_raw and isinstance(metrics_raw, dict):
        await store.set_metrics(
            FlowMetrics(
                metrics_id=metrics_raw.get("metrics_id", str(uuid4())),
                flow_map_id=flow_map_id,
                total_flows=metrics_raw.get("total_flows", 0),
                flows_by_type=metrics_raw.get("flows_by_type", {}),
                avg_depth=metrics_raw.get("avg_depth", 0.0),
                max_depth=metrics_raw.get("max_depth", 0),
                complexity_score=metrics_raw.get("complexity_score", 0.0),
            )
        )

    await tracker.append_log(
        "persist_results",
        f"Persisted: {len(flow_entries)} flows, {len(diagram_entries)} diagrams.",
    )
    await tracker.mark_completed(
        "persist_results",
        outputs={
            "map_id": flow_map_id,
            "flow_count": len(flow_entries),
            "diagram_count": len(diagram_entries),
        },
    )

    return {"status": "completed"}


async def error_node(
    state: ProcessMiningState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Handle workflow-level failures."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    errors = state.get("errors") or []
    logger.error("process_mining_error", errors=errors)
    await tracker.append_log("error", f"Workflow failed with {len(errors)} error(s).")

    return {"status": "failed"}


# ---------------------------------------------------------------------------
# Check phase helper
# ---------------------------------------------------------------------------


def _check_phase(state: ProcessMiningState) -> str:
    """Route to error_node if the workflow has accumulated errors and status is failed."""
    if state.get("status") == "failed":
        return "error"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_process_mining_graph() -> StateGraph[Any]:
    """Build the process-mining workflow graph.

    Pipeline: ingest -> setup_workspace -> discover_endpoints -> trace_flows
              -> classify_flows -> generate_diagrams -> persist_results
    with error routing after discover_endpoints.
    """
    from lintel.workflows.nodes.ingest import ingest_message
    from lintel.workflows.nodes.setup_workspace import setup_workspace

    g: StateGraph[Any] = StateGraph(ProcessMiningState)

    # Nodes
    g.add_node("ingest", ingest_message)  # type: ignore[arg-type]
    g.add_node("setup_workspace", setup_workspace)  # type: ignore[arg-type]
    g.add_node("discover_endpoints", discover_endpoints_node)  # type: ignore[arg-type]
    g.add_node("trace_flows", trace_flows_node)  # type: ignore[arg-type]
    g.add_node("classify_flows", classify_flows_node)  # type: ignore[arg-type]
    g.add_node("generate_diagrams", generate_diagrams_node)  # type: ignore[arg-type]
    g.add_node("persist_results", persist_results_node)  # type: ignore[arg-type]
    g.add_node("error", error_node)  # type: ignore[arg-type]

    # Entry
    g.set_entry_point("ingest")

    # Edges
    g.add_edge("ingest", "setup_workspace")
    g.add_edge("setup_workspace", "discover_endpoints")
    g.add_conditional_edges(
        "discover_endpoints",
        _check_phase,
        {"continue": "trace_flows", "error": "error"},
    )
    g.add_edge("trace_flows", "classify_flows")
    g.add_edge("classify_flows", "generate_diagrams")
    g.add_edge("generate_diagrams", "persist_results")
    g.add_edge("persist_results", END)
    g.add_edge("error", END)

    return g
