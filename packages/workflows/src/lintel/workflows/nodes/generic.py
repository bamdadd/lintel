"""Generic / stub workflow nodes for templates that don't need complex logic yet.

Each function is a thin async node that sets current_phase and appends to agent_outputs.
These will be replaced with real LLM/sandbox-backed implementations as needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


def _stub(
    node_name: str, phase: str, summary: str
) -> Callable[..., Coroutine[object, object, dict[str, Any]]]:
    """Create a stub node function."""

    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "current_phase": phase,
            "agent_outputs": [{"node": node_name, "summary": summary}],
        }

    _node.__name__ = node_name
    _node.__qualname__ = node_name
    return _node


# Bug-fix nodes
reproduce_bug = _stub("reproduce", "reproducing", "Bug reproduction attempted")
fix_bug = _stub("fix", "fixing", "Fix applied")

# Code review nodes
lint_code = _stub("lint", "linting", "Lint checks passed")
security_scan = _stub("security_scan", "scanning", "Security scan complete")
send_feedback = _stub("feedback", "feedback", "Review feedback sent")

# Refactor nodes
refactor_code = _stub("refactor", "refactoring", "Refactoring complete")

# Security audit nodes
dependency_scan = _stub("dependency_scan", "scanning", "Dependency scan complete")
code_scan = _stub("code_scan", "scanning", "Code scan complete")
secret_scan = _stub("secret_scan", "scanning", "Secret scan complete")
generate_report = _stub("report", "reporting", "Report generated")
remediate = _stub("remediate", "remediating", "Remediation applied")

# Incident response nodes
investigate = _stub("investigate", "investigating", "Investigation complete")
hotfix = _stub("hotfix", "hotfixing", "Hotfix applied")
deploy = _stub("deploy", "deploying", "Deployment complete")
post_mortem = _stub("post_mortem", "post_mortem", "Post-mortem written")

# Documentation nodes
draft_docs = _stub("draft", "drafting", "Documentation drafted")
publish_docs = _stub("publish", "publishing", "Documentation published")

# Release nodes
write_changelog = _stub("changelog", "changelog", "Changelog generated")
version_bump = _stub("version_bump", "versioning", "Version bumped")
build_release = _stub("build", "building", "Build complete")
notify_release = _stub("notify", "notifying", "Notifications sent")

# Onboarding nodes
setup_env = _stub("setup", "setup", "Environment setup complete")
codebase_tour = _stub("codebase_tour", "touring", "Codebase tour complete")
first_task = _stub("first_task", "first_task", "First task assigned")
complete_onboarding = _stub("complete", "complete", "Onboarding complete")

# Spike nodes
define_scope = _stub("define_scope", "scoping", "Scope defined")
research = _stub("research", "researching", "Research complete")
prototype = _stub("prototype", "prototyping", "Prototype built")
