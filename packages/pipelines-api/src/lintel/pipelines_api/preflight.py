"""Pre-flight checks before dispatching a workflow.

Validates that the pipeline has everything it needs to succeed,
catching common failures (missing repo URL, missing project) early.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Workflows that operate on code and require at least one repository URL.
_CODE_WORKFLOWS = frozenset(
    {
        "feature_to_pr",
        "bug_fix",
        "refactor",
    }
)


@dataclass
class PreflightResult:
    """Result of running pre-flight checks.

    Errors are hard failures — the pipeline should not be dispatched.
    Warnings are advisory — dispatch proceeds but caller should log them.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


async def run_preflight_checks(
    *,
    workflow_type: str,
    repo_url: str = "",
    repo_urls: tuple[str, ...] = (),
    project_id: str = "",
) -> PreflightResult:
    """Run pre-flight validation before dispatching a workflow.

    Args:
        workflow_type: The workflow definition ID (e.g. "feature_to_pr").
        repo_url: Primary repository URL resolved from the project.
        repo_urls: All repository URLs for multi-repo workflows.
        project_id: The project ID associated with this pipeline.

    Returns:
        PreflightResult with any errors and warnings found.
    """
    result = PreflightResult()

    # Check: code workflows require a repository URL
    if workflow_type in _CODE_WORKFLOWS:
        has_repo = bool(repo_url) or bool(repo_urls)
        if not has_repo:
            result.errors.append(
                f"No repository URL configured for code workflow '{workflow_type}'. "
                "Attach a repository to the project before running this workflow."
            )

    # Check: project_id should be set
    if not project_id:
        result.warnings.append(
            "No project ID specified. Pipeline will run without project context."
        )

    return result
