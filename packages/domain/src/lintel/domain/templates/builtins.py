"""Built-in workflow templates."""

from __future__ import annotations

from lintel.domain.templates.types import (
    StageConfig,
    TemplateCategory,
    TemplateParameter,
    WorkflowTemplate,
)

FEATURE_TO_PR = WorkflowTemplate(
    id="feature_to_pr",
    name="Feature to PR",
    description=("End-to-end feature implementation: research, plan, implement, review, raise PR."),
    category=TemplateCategory.FEATURE,
    stages=(
        StageConfig(name="ingest", stage_type="ingest", description="Parse and enrich request"),
        StageConfig(name="route", stage_type="route", description="Select workflow path"),
        StageConfig(
            name="setup_workspace", stage_type="setup", description="Prepare sandbox workspace"
        ),
        StageConfig(name="research", stage_type="research", description="Analyse codebase"),
        StageConfig(
            name="approve_research",
            stage_type="approval",
            description="Human approves research findings",
            requires_approval=True,
        ),
        StageConfig(name="plan", stage_type="plan", description="Generate implementation plan"),
        StageConfig(
            name="approve_spec",
            stage_type="approval",
            description="Human approves specification",
            requires_approval=True,
        ),
        StageConfig(name="implement", stage_type="implement", description="Write code changes"),
        StageConfig(name="review", stage_type="review", description="Automated code review"),
        StageConfig(
            name="approved_for_pr",
            stage_type="approval",
            description="Human approves PR creation",
            requires_approval=True,
        ),
        StageConfig(name="raise_pr", stage_type="merge", description="Create pull request"),
    ),
    default_config={"max_review_cycles": 2, "sandbox_type": "docker"},
    parameters=(
        TemplateParameter(
            name="branch_prefix",
            type="str",
            default_value="feat/",
            description="Branch name prefix",
        ),
        TemplateParameter(
            name="max_review_cycles",
            type="int",
            default_value=2,
            description="Maximum review-implement cycles",
        ),
        TemplateParameter(
            name="repo_url",
            type="str",
            required=True,
            description="Repository URL to work on",
        ),
    ),
    tags=("feature", "pr", "implementation"),
    version="1.0.0",
)

CODE_REVIEW = WorkflowTemplate(
    id="code_review",
    name="Code Review",
    description="Automated code review of an existing branch or PR.",
    category=TemplateCategory.REVIEW,
    stages=(
        StageConfig(name="ingest", stage_type="ingest", description="Fetch PR/branch details"),
        StageConfig(name="setup_workspace", stage_type="setup", description="Clone and checkout"),
        StageConfig(name="review", stage_type="review", description="Run automated review checks"),
        StageConfig(name="report", stage_type="report", description="Generate review summary"),
    ),
    default_config={"review_depth": "standard"},
    parameters=(
        TemplateParameter(
            name="pr_url",
            type="str",
            required=True,
            description="Pull request URL to review",
        ),
        TemplateParameter(
            name="review_depth",
            type="str",
            default_value="standard",
            description="Review depth: quick, standard, thorough",
        ),
    ),
    tags=("review", "quality"),
    version="1.0.0",
)

INCIDENT_RESPONSE = WorkflowTemplate(
    id="incident_response",
    name="Incident Response",
    description="Triage, diagnose, and remediate a production incident.",
    category=TemplateCategory.BUGFIX,
    stages=(
        StageConfig(name="triage", stage_type="ingest", description="Assess incident severity"),
        StageConfig(name="diagnose", stage_type="research", description="Root cause analysis"),
        StageConfig(
            name="approve_fix",
            stage_type="approval",
            description="Approve proposed fix",
            requires_approval=True,
        ),
        StageConfig(name="implement_fix", stage_type="implement", description="Apply hotfix"),
        StageConfig(name="verify", stage_type="review", description="Verify fix in staging"),
        StageConfig(name="deploy", stage_type="merge", description="Deploy hotfix"),
    ),
    default_config={"severity": "p2", "notify_channel": "incidents"},
    parameters=(
        TemplateParameter(
            name="incident_url",
            type="str",
            required=True,
            description="Link to incident report or alert",
        ),
        TemplateParameter(
            name="severity",
            type="str",
            default_value="p2",
            description="Incident severity: p1, p2, p3",
        ),
        TemplateParameter(
            name="notify_channel",
            type="str",
            default_value="incidents",
            description="Slack channel for notifications",
        ),
    ),
    tags=("incident", "bugfix", "hotfix"),
    version="1.0.0",
)

BUILTIN_TEMPLATES: tuple[WorkflowTemplate, ...] = (
    FEATURE_TO_PR,
    CODE_REVIEW,
    INCIDENT_RESPONSE,
)
