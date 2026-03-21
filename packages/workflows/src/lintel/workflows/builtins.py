"""Built-in node and router registration for REQ-020.

Single source of truth for all out-of-the-box workflow stage types.
Call ``register_builtin_nodes`` and ``register_builtin_routers`` at app
startup to populate the singletons before any compilation or API request.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from lintel.workflows.node_descriptor import NodeDescriptor

if TYPE_CHECKING:
    from lintel.workflows.node_registry import NodeRegistry
    from lintel.workflows.router_factory import RouterFactory


# ---------------------------------------------------------------------------
# Router functions (match LangGraph ``(state) -> str`` signature)
# ---------------------------------------------------------------------------


def _route_decision(state: dict[str, Any]) -> str:
    """Route after ingest: actionable intents → setup_workspace, else close."""
    intent = state.get("intent", "")
    if intent in ("feature", "bug", "refactor"):
        return "setup_workspace"
    return "close"


def _check_phase(state: dict[str, Any]) -> str:
    """Stop the pipeline on error or failed verdict."""
    if state.get("error"):
        return "close"
    if state.get("current_phase") == "closed":
        return "close"
    for output in reversed(state.get("agent_outputs", [])):
        if isinstance(output, dict) and output.get("verdict") == "failed":
            return "close"
    return "continue"


def _review_decision(state: dict[str, Any]) -> str:
    """After review: approve → continue, request_changes → revise (cycle-limited)."""
    max_review_cycles = 5
    if state.get("error"):
        return "close"
    review_cycles = state.get("review_cycles", 0)
    for output in reversed(state.get("agent_outputs", [])):
        if not isinstance(output, dict):
            continue
        if output.get("node") != "review":
            continue
        if output.get("verdict") == "request_changes":
            if review_cycles < max_review_cycles:
                return "revise"
            return "close"
        if output.get("verdict") == "approve":
            return "continue"
        break
    return "continue"


def _default_linear(_state: dict[str, Any]) -> str:
    """Always return 'continue' — useful as a no-op conditional edge."""
    return "continue"


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def _gate(gate_type: str) -> Any:  # noqa: ANN401
    """Create an approval gate partial for a specific gate type."""
    from lintel.workflows.nodes.approval_gate import approval_gate

    return partial(approval_gate, gate_type=gate_type)


def register_builtin_nodes(registry: NodeRegistry) -> None:
    """Register all built-in workflow node types into *registry*."""
    from lintel.workflows.nodes.close import close_workflow
    from lintel.workflows.nodes.generic import (
        build_release,
        code_scan,
        codebase_tour,
        complete_onboarding,
        define_scope,
        dependency_scan,
        deploy,
        draft_docs,
        first_task,
        fix_bug,
        hotfix,
        investigate,
        lint_code,
        notify_release,
        post_mortem,
        prototype,
        publish_docs,
        refactor_code,
        remediate,
        reproduce_bug,
        research,
        secret_scan,
        security_scan,
        send_feedback,
        setup_env,
        version_bump,
        write_changelog,
    )
    from lintel.workflows.nodes.generic import generate_report as report_node
    from lintel.workflows.nodes.implement import spawn_implementation
    from lintel.workflows.nodes.ingest import ingest_message
    from lintel.workflows.nodes.plan import plan_work
    from lintel.workflows.nodes.research import research_codebase
    from lintel.workflows.nodes.review import review_output
    from lintel.workflows.nodes.route import route_intent
    from lintel.workflows.nodes.setup_workspace import setup_workspace
    from lintel.workflows.nodes.test_code import run_tests
    from lintel.workflows.nodes.triage import triage_issue

    _nodes: list[tuple[NodeDescriptor, Any]] = [
        # ---- Feature-to-PR core nodes ----
        (
            NodeDescriptor(
                node_type="ingest",
                display_name="Ingest Message",
                description="Process incoming message through PII firewall and normalise.",
                tags=("core", "input"),
            ),
            ingest_message,
        ),
        (
            NodeDescriptor(
                node_type="route",
                display_name="Route Intent",
                description="Classify user intent (feature, bug, refactor) and route.",
                router_type="route_decision",
                output_edges=("setup_workspace", "close"),
                tags=("core", "routing"),
            ),
            route_intent,
        ),
        (
            NodeDescriptor(
                node_type="setup_workspace",
                display_name="Setup Workspace",
                description="Clone repo, create sandbox, configure credentials.",
                tags=("core", "setup"),
            ),
            setup_workspace,
        ),
        (
            NodeDescriptor(
                node_type="research",
                display_name="Research Codebase",
                description="Survey codebase for context before planning.",
                tags=("core", "analysis"),
            ),
            research_codebase,
        ),
        (
            NodeDescriptor(
                node_type="plan",
                display_name="Plan Work",
                description="Generate implementation plan via planner agent.",
                tags=("core", "planning"),
            ),
            plan_work,
        ),
        (
            NodeDescriptor(
                node_type="implement",
                display_name="Implement",
                description="Generate code changes following the plan.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("core", "coding"),
            ),
            spawn_implementation,
        ),
        (
            NodeDescriptor(
                node_type="review",
                display_name="Code Review",
                description="Review code changes for correctness and quality.",
                router_type="review_decision",
                output_edges=("continue", "revise", "close"),
                tags=("core", "quality"),
            ),
            review_output,
        ),
        (
            NodeDescriptor(
                node_type="close",
                display_name="Close Workflow",
                description="Commit, push, create PR, and finalise the workflow.",
                tags=("core", "output"),
            ),
            close_workflow,
        ),
        (
            NodeDescriptor(
                node_type="test",
                display_name="Run Tests",
                description="Execute test suite in sandbox environment.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("core", "testing"),
            ),
            run_tests,
        ),
        # ---- Approval gates ----
        (
            NodeDescriptor(
                node_type="approval_gate_research",
                display_name="Research Approval Gate",
                description="Human approval gate after research phase.",
                tags=("gate",),
            ),
            _gate("research_approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate_spec",
                display_name="Spec Approval Gate",
                description="Human approval gate for the implementation spec.",
                tags=("gate",),
            ),
            _gate("spec_approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate_pr",
                display_name="PR Approval Gate",
                description="Human approval gate before PR merge.",
                tags=("gate",),
            ),
            _gate("pr_approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate_deploy",
                display_name="Deploy Approval Gate",
                description="Human approval gate before deployment.",
                tags=("gate",),
            ),
            _gate("deploy_approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate_release",
                display_name="Release Approval Gate",
                description="Human approval gate before release.",
                tags=("gate",),
            ),
            _gate("release_approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate",
                display_name="Approval Gate",
                description="Generic human approval gate.",
                tags=("gate",),
            ),
            _gate("approval"),
        ),
        (
            NodeDescriptor(
                node_type="approval_gate_merge",
                display_name="Merge Approval Gate",
                description="Human approval gate before merge.",
                tags=("gate",),
            ),
            _gate("merge_approval"),
        ),
        # ---- Triage / bug-fix ----
        (
            NodeDescriptor(
                node_type="triage",
                display_name="Triage Issue",
                description="Classify issue type, severity, and priority.",
                tags=("triage",),
            ),
            triage_issue,
        ),
        (
            NodeDescriptor(
                node_type="reproduce",
                display_name="Reproduce Bug",
                description="Attempt to reproduce the reported bug.",
                tags=("bugfix",),
            ),
            reproduce_bug,
        ),
        (
            NodeDescriptor(
                node_type="fix",
                display_name="Fix Bug",
                description="Apply a fix for the reproduced bug.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("bugfix",),
            ),
            fix_bug,
        ),
        # ---- Code review ----
        (
            NodeDescriptor(
                node_type="lint",
                display_name="Lint Code",
                description="Run linting checks on the codebase.",
                tags=("quality",),
            ),
            lint_code,
        ),
        (
            NodeDescriptor(
                node_type="security_scan",
                display_name="Security Scan",
                description="Run security vulnerability scan.",
                tags=("security",),
            ),
            security_scan,
        ),
        (
            NodeDescriptor(
                node_type="feedback",
                display_name="Send Feedback",
                description="Send review feedback to the team.",
                tags=("communication",),
            ),
            send_feedback,
        ),
        # ---- Refactor ----
        (
            NodeDescriptor(
                node_type="refactor",
                display_name="Refactor Code",
                description="Apply refactoring changes to the codebase.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("refactor",),
            ),
            refactor_code,
        ),
        # ---- Security audit ----
        (
            NodeDescriptor(
                node_type="dependency_scan",
                display_name="Dependency Scan",
                description="Scan project dependencies for known vulnerabilities.",
                tags=("security",),
            ),
            dependency_scan,
        ),
        (
            NodeDescriptor(
                node_type="code_scan",
                display_name="Code Scan",
                description="Static analysis scan of the codebase.",
                tags=("security",),
            ),
            code_scan,
        ),
        (
            NodeDescriptor(
                node_type="secret_scan",
                display_name="Secret Scan",
                description="Scan for exposed secrets and credentials.",
                tags=("security",),
            ),
            secret_scan,
        ),
        (
            NodeDescriptor(
                node_type="report",
                display_name="Generate Report",
                description="Generate a summary report of findings.",
                tags=("reporting",),
            ),
            report_node,
        ),
        (
            NodeDescriptor(
                node_type="remediate",
                display_name="Remediate",
                description="Apply remediation for identified issues.",
                tags=("security",),
            ),
            remediate,
        ),
        # ---- Incident response ----
        (
            NodeDescriptor(
                node_type="investigate",
                display_name="Investigate",
                description="Investigate the root cause of an incident.",
                tags=("incident",),
            ),
            investigate,
        ),
        (
            NodeDescriptor(
                node_type="hotfix",
                display_name="Hotfix",
                description="Apply a hotfix for the incident.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("incident",),
            ),
            hotfix,
        ),
        (
            NodeDescriptor(
                node_type="deploy",
                display_name="Deploy",
                description="Deploy changes to the target environment.",
                tags=("deployment",),
            ),
            deploy,
        ),
        (
            NodeDescriptor(
                node_type="post_mortem",
                display_name="Post-Mortem",
                description="Write post-mortem analysis of the incident.",
                tags=("incident",),
            ),
            post_mortem,
        ),
        # ---- Documentation ----
        (
            NodeDescriptor(
                node_type="draft",
                display_name="Draft Docs",
                description="Draft technical documentation.",
                tags=("documentation",),
            ),
            draft_docs,
        ),
        (
            NodeDescriptor(
                node_type="publish",
                display_name="Publish Docs",
                description="Publish documentation to the target platform.",
                tags=("documentation",),
            ),
            publish_docs,
        ),
        # ---- Release ----
        (
            NodeDescriptor(
                node_type="changelog",
                display_name="Write Changelog",
                description="Generate changelog from recent changes.",
                tags=("release",),
            ),
            write_changelog,
        ),
        (
            NodeDescriptor(
                node_type="version_bump",
                display_name="Version Bump",
                description="Bump project version number.",
                tags=("release",),
            ),
            version_bump,
        ),
        (
            NodeDescriptor(
                node_type="build",
                display_name="Build Release",
                description="Build release artifacts.",
                router_type="check_phase",
                output_edges=("continue", "close"),
                tags=("release",),
            ),
            build_release,
        ),
        (
            NodeDescriptor(
                node_type="notify",
                display_name="Notify Release",
                description="Send release notifications.",
                tags=("release", "communication"),
            ),
            notify_release,
        ),
        # ---- Onboarding ----
        (
            NodeDescriptor(
                node_type="setup",
                display_name="Setup Environment",
                description="Setup development environment for onboarding.",
                tags=("onboarding",),
            ),
            setup_env,
        ),
        (
            NodeDescriptor(
                node_type="codebase_tour",
                display_name="Codebase Tour",
                description="Guided tour of the codebase architecture.",
                tags=("onboarding",),
            ),
            codebase_tour,
        ),
        (
            NodeDescriptor(
                node_type="first_task",
                display_name="First Task",
                description="Assign and guide through the first task.",
                tags=("onboarding",),
            ),
            first_task,
        ),
        (
            NodeDescriptor(
                node_type="complete",
                display_name="Complete Onboarding",
                description="Finalise the onboarding process.",
                tags=("onboarding",),
            ),
            complete_onboarding,
        ),
        # ---- Spike ----
        (
            NodeDescriptor(
                node_type="define_scope",
                display_name="Define Scope",
                description="Define scope and goals for a technical spike.",
                tags=("spike",),
            ),
            define_scope,
        ),
        (
            NodeDescriptor(
                node_type="research_generic",
                display_name="Research",
                description="Conduct research for a technical spike.",
                tags=("spike",),
            ),
            research,
        ),
        (
            NodeDescriptor(
                node_type="prototype",
                display_name="Prototype",
                description="Build a prototype or proof of concept.",
                tags=("spike",),
            ),
            prototype,
        ),
    ]

    for descriptor, handler in _nodes:
        registry.register(descriptor, handler)


def register_builtin_routers(factory: RouterFactory) -> None:
    """Register all built-in conditional-edge routers into *factory*."""
    factory.register_router("route_decision", _route_decision)
    factory.register_router("check_phase", _check_phase)
    factory.register_router("review_decision", _review_decision)
    factory.register_router("default_linear", _default_linear)


def ensure_builtins_registered() -> None:
    """Ensure the module-level singletons are populated (idempotent)."""
    from lintel.workflows.node_registry import node_registry
    from lintel.workflows.router_factory import router_factory

    if len(node_registry) == 0:
        register_builtin_nodes(node_registry)
    if len(router_factory) == 0:
        register_builtin_routers(router_factory)
