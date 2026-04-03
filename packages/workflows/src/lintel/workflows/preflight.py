"""Pre-flight checks before dispatching a workflow.

Validates that the pipeline has everything it needs to succeed,
catching common failures (missing repo URL, missing credentials) early.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Workflows that operate on code and require at least one repository URL.
CODE_WORKFLOWS = frozenset(
    {
        "feature_to_pr",
        "feature",
        "bug_fix",
        "code_review",
        "refactor",
        "security_audit",
        "incident_response",
        "release",
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
    credential_ids: tuple[str, ...] = (),
    credential_store: Any = None,  # noqa: ANN401
    sandbox_manager: Any = None,  # noqa: ANN401
) -> PreflightResult:
    """Run pre-flight validation before dispatching a workflow.

    Args:
        workflow_type: The workflow definition ID (e.g. "feature_to_pr").
        repo_url: Primary repository URL resolved from the project.
        repo_urls: All repository URLs for multi-repo workflows.
        project_id: The project ID associated with this pipeline.
        credential_ids: Credential IDs the workflow expects to use.
        credential_store: Optional credential store for validating IDs exist.
        sandbox_manager: Optional sandbox manager to check availability.

    Returns:
        PreflightResult with any errors and warnings found.
    """
    result = PreflightResult()

    # 1. Code workflows require a repository URL
    is_code_workflow = workflow_type in CODE_WORKFLOWS
    if is_code_workflow:
        has_repo = bool(repo_url) or bool(repo_urls)
        if not has_repo:
            result.errors.append(
                f"No repository URL configured for code workflow '{workflow_type}'. "
                "Attach a repository to the project before running this workflow."
            )

    # 2. Project ID should be set
    if not project_id:
        result.warnings.append(
            "No project ID specified. Pipeline will run without project context."
        )

    # 3. Credential IDs must resolve to existing credentials
    if credential_ids and credential_store is not None:
        for cred_id in credential_ids:
            try:
                cred = await credential_store.get(cred_id)
                if cred is None:
                    result.errors.append(
                        f"Credential '{cred_id}' not found. "
                        "Store it via /settings/credentials before dispatching."
                    )
            except Exception:
                result.errors.append(
                    f"Failed to look up credential '{cred_id}'. "
                    "Credential store may be unavailable."
                )

    # 4. Sandbox availability — warn but don't block (sandbox may free up)
    if is_code_workflow and sandbox_manager is None:
        result.warnings.append(
            "No sandbox manager configured. Code execution may fail during workflow."
        )

    return result
