"""Workflow graph registry — maps definition IDs to LangGraph builders.

Each builder returns a StateGraph that can be compiled with a checkpointer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from langgraph.graph import END, StateGraph

from lintel.workflows.nodes.analyse import analyse_code
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
from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.test_code import run_tests
from lintel.workflows.nodes.triage import triage_issue
from lintel.workflows.state import ThreadWorkflowState

_PASS = lambda s: s  # noqa: E731  — approval gate passthrough


def _gate(name: str) -> Any:  # noqa: ANN401
    """Named passthrough for approval gates."""
    fn = lambda s: s  # noqa: E731
    fn.__name__ = name
    fn.__qualname__ = name
    return fn


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_bug_fix_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("triage", triage_issue)
    g.add_node("reproduce", reproduce_bug)
    g.add_node("fix", fix_bug)
    g.add_node("test", run_tests)
    g.add_node("review", review_output)
    g.add_node("approval_gate_merge", _gate("approval_gate_merge"))
    g.add_node("close", lambda s: {**s, "current_phase": "closed"})
    g.set_entry_point("triage")
    g.add_edge("triage", "reproduce")
    g.add_edge("reproduce", "fix")
    g.add_edge("fix", "test")
    g.add_edge("test", "review")
    g.add_edge("review", "approval_gate_merge")
    g.add_edge("approval_gate_merge", "close")
    g.add_edge("close", END)
    return g


def build_code_review_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("lint", lint_code)
    g.add_node("security_scan", security_scan)
    g.add_node("review", review_output)
    g.add_node("feedback", send_feedback)
    g.set_entry_point("lint")
    g.add_edge("lint", "security_scan")
    g.add_edge("security_scan", "review")
    g.add_edge("review", "feedback")
    g.add_edge("feedback", END)
    return g


def build_refactor_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("analyse", analyse_code)
    g.add_node("plan", plan_work)
    g.add_node("approval_gate_spec", _gate("approval_gate_spec"))
    g.add_node("refactor", refactor_code)
    g.add_node("test", run_tests)
    g.add_node("review", review_output)
    g.add_node("approval_gate_merge", _gate("approval_gate_merge"))
    g.add_node("close", lambda s: {**s, "current_phase": "closed"})
    g.set_entry_point("analyse")
    g.add_edge("analyse", "plan")
    g.add_edge("plan", "approval_gate_spec")
    g.add_edge("approval_gate_spec", "refactor")
    g.add_edge("refactor", "test")
    g.add_edge("test", "review")
    g.add_edge("review", "approval_gate_merge")
    g.add_edge("approval_gate_merge", "close")
    g.add_edge("close", END)
    return g


def build_security_audit_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("dependency_scan", dependency_scan)
    g.add_node("code_scan", code_scan)
    g.add_node("secret_scan", secret_scan)
    g.add_node("report", report_node)
    g.add_node("approval_gate", _gate("approval_gate"))
    g.add_node("remediate", remediate)
    g.set_entry_point("dependency_scan")
    g.add_edge("dependency_scan", "code_scan")
    g.add_edge("code_scan", "secret_scan")
    g.add_edge("secret_scan", "report")
    g.add_edge("report", "approval_gate")
    g.add_edge("approval_gate", "remediate")
    g.add_edge("remediate", END)
    return g


def build_incident_response_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("triage", triage_issue)
    g.add_node("investigate", investigate)
    g.add_node("hotfix", hotfix)
    g.add_node("test", run_tests)
    g.add_node("approval_gate_deploy", _gate("approval_gate_deploy"))
    g.add_node("deploy", deploy)
    g.add_node("post_mortem", post_mortem)
    g.set_entry_point("triage")
    g.add_edge("triage", "investigate")
    g.add_edge("investigate", "hotfix")
    g.add_edge("hotfix", "test")
    g.add_edge("test", "approval_gate_deploy")
    g.add_edge("approval_gate_deploy", "deploy")
    g.add_edge("deploy", "post_mortem")
    g.add_edge("post_mortem", END)
    return g


def build_documentation_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("analyse", analyse_code)
    g.add_node("draft", draft_docs)
    g.add_node("review", review_output)
    g.add_node("publish", publish_docs)
    g.set_entry_point("analyse")
    g.add_edge("analyse", "draft")
    g.add_edge("draft", "review")
    g.add_edge("review", "publish")
    g.add_edge("publish", END)
    return g


def build_release_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("changelog", write_changelog)
    g.add_node("version_bump", version_bump)
    g.add_node("build", build_release)
    g.add_node("test", run_tests)
    g.add_node("approval_gate_release", _gate("approval_gate_release"))
    g.add_node("deploy", deploy)
    g.add_node("notify", notify_release)
    g.set_entry_point("changelog")
    g.add_edge("changelog", "version_bump")
    g.add_edge("version_bump", "build")
    g.add_edge("build", "test")
    g.add_edge("test", "approval_gate_release")
    g.add_edge("approval_gate_release", "deploy")
    g.add_edge("deploy", "notify")
    g.add_edge("notify", END)
    return g


def build_onboarding_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("setup", setup_env)
    g.add_node("codebase_tour", codebase_tour)
    g.add_node("first_task", first_task)
    g.add_node("review", review_output)
    g.add_node("complete", complete_onboarding)
    g.set_entry_point("setup")
    g.add_edge("setup", "codebase_tour")
    g.add_edge("codebase_tour", "first_task")
    g.add_edge("first_task", "review")
    g.add_edge("review", "complete")
    g.add_edge("complete", END)
    return g


def build_spike_graph() -> StateGraph[Any]:
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)
    g.add_node("define_scope", define_scope)
    g.add_node("research", research)
    g.add_node("prototype", prototype)
    g.add_node("report", report_node)
    g.set_entry_point("define_scope")
    g.add_edge("define_scope", "research")
    g.add_edge("research", "prototype")
    g.add_edge("prototype", "report")
    g.add_edge("report", END)
    return g


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

WORKFLOW_BUILDERS: dict[str, Any] = {
    "feature_to_pr": None,  # uses dedicated module
    "bug_fix": build_bug_fix_graph,
    "code_review": build_code_review_graph,
    "refactor": build_refactor_graph,
    "security_audit": build_security_audit_graph,
    "incident_response": build_incident_response_graph,
    "documentation": build_documentation_graph,
    "release": build_release_graph,
    "onboarding": build_onboarding_graph,
    "spike": build_spike_graph,
}


def get_workflow_builder(definition_id: str) -> Callable[[], StateGraph[Any]]:
    """Get the graph builder function for a workflow definition."""
    if definition_id == "feature_to_pr":
        from lintel.workflows.feature_to_pr import build_feature_to_pr_graph

        return build_feature_to_pr_graph

    builder = WORKFLOW_BUILDERS.get(definition_id)
    if builder is None:
        msg = f"Unknown workflow definition: {definition_id}"
        raise KeyError(msg)
    return builder  # type: ignore[no-any-return]
