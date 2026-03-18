"""Default workflow definitions — engineering team pipelines."""

from __future__ import annotations

from lintel.workflows.types import WorkflowDefinitionRecord

DEFAULT_WORKFLOW_DEFINITIONS: tuple[WorkflowDefinitionRecord, ...] = (
    WorkflowDefinitionRecord(
        definition_id="feature_to_pr",
        name="Feature to PR",
        description=(
            "End-to-end feature implementation: research, plan, implement, review, raise PR."
        ),
        is_template=True,
        stage_names=(
            "ingest",
            "route",
            "setup_workspace",
            "research",
            "approve_research",
            "plan",
            "approve_spec",
            "implement",
            "review",
            "approved_for_pr",
            "raise_pr",
        ),
        graph_nodes=(
            "ingest",
            "route",
            "setup_workspace",
            "research",
            "approval_gate_research",
            "plan",
            "approval_gate_spec",
            "implement",
            "review",
            "approval_gate_pr",
            "close",
        ),
        graph_edges=(
            ("ingest", "route"),
            ("setup_workspace", "research"),
            ("research", "approval_gate_research"),
            ("approval_gate_research", "plan"),
            ("plan", "approval_gate_spec"),
            ("approval_gate_spec", "implement"),
            ("approval_gate_pr", "close"),
        ),
        conditional_edges=(
            {
                "source": "route",
                "targets": {"setup_workspace": "setup_workspace", "close": "close"},
            },
            {
                "source": "implement",
                "targets": {"continue": "review", "close": "close"},
            },
            {
                "source": "review",
                "targets": {
                    "continue": "approval_gate_pr",
                    "revise": "implement",
                    "close": "close",
                },
            },
        ),
        entry_point="ingest",
        interrupt_before=(
            "approval_gate_research",
            "approval_gate_spec",
            "approval_gate_pr",
        ),
        node_metadata=(
            {
                "node": "ingest",
                "label": "Ingest",
                "agent": "system",
                "description": (
                    "Receives and sanitises the user request."
                    " Strips PII and normalises the message for downstream nodes."
                ),
            },
            {
                "node": "route",
                "label": "Route Intent",
                "agent": "triage",
                "agent_id": "agent_triage",
                "description": (
                    "Classifies the request as feature, bug, or refactor and decides whether to"
                    " plan or close."
                ),
            },
            {
                "node": "setup_workspace",
                "label": "Setup Workspace",
                "agent": "system",
                "description": (
                    "Clones the project repository into a sandbox and creates a feature branch."
                ),
            },
            {
                "node": "research",
                "label": "Research",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Surveys the codebase structure, key files, and patterns to build context"
                    " for the planning stage."
                ),
            },
            {
                "node": "plan",
                "label": "Plan",
                "agent": "planner",
                "agent_id": "agent_planner",
                "description": (
                    "Calls the Planner agent to break down the request into numbered tasks with"
                    " complexity estimates and affected files."
                ),
            },
            {
                "node": "approval_gate_spec",
                "label": "Approve Spec",
                "agent": "human",
                "description": (
                    "Pauses the workflow for a human to review and approve the generated plan"
                    " before implementation begins."
                ),
            },
            {
                "node": "implement",
                "label": "Implement",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": (
                    "Executes the plan in an isolated sandbox: writes code, edits files, and"
                    " collects artefacts."
                ),
            },
            {
                "node": "test",
                "label": "Test",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": (
                    "Runs the test suite against the implementation and reports pass/fail verdicts."
                ),
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": (
                    "Performs an automated code review on the diff, checking for quality, style,"
                    " and correctness."
                ),
            },
            {
                "node": "approval_gate_pr",
                "label": "Approved for PR",
                "agent": "human",
                "description": (
                    "Pauses the workflow for a human to approve before raising a pull request."
                ),
            },
            {
                "node": "close",
                "label": "Raise PR",
                "agent": "system",
                "description": (
                    "Creates a branch, commits changes, pushes to GitHub,"
                    " and raises a pull request."
                ),
            },
        ),
        tags=("feature", "full-pipeline"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="bug_fix",
        name="Bug Fix",
        description=("Triage, reproduce, fix, test, and review a bug report."),
        is_template=True,
        stage_names=(
            "triage",
            "reproduce",
            "fix",
            "test",
            "review",
            "approved_for_pr",
            "raise_pr",
        ),
        graph_nodes=(
            "triage",
            "reproduce",
            "fix",
            "test",
            "review",
            "approval_gate_pr",
            "close",
        ),
        graph_edges=(
            ("triage", "reproduce"),
            ("reproduce", "fix"),
            ("fix", "test"),
            ("test", "review"),
            ("review", "approval_gate_pr"),
            ("approval_gate_pr", "close"),
        ),
        entry_point="triage",
        interrupt_before=("approval_gate_pr",),
        node_metadata=(
            {
                "node": "triage",
                "label": "Triage",
                "agent": "triage",
                "agent_id": "agent_triage",
                "description": (
                    "Assesses severity and priority of the bug report and assigns initial labels."
                ),
            },
            {
                "node": "reproduce",
                "label": "Reproduce",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": (
                    "Attempts to reproduce the bug with minimal steps and confirms the failure"
                    " condition."
                ),
            },
            {
                "node": "fix",
                "label": "Fix",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": (
                    "Implements the bug fix in an isolated sandbox based on the reproduction"
                    " findings."
                ),
            },
            {
                "node": "test",
                "label": "Test",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": (
                    "Runs regression tests to verify the fix and ensure no new breakages."
                ),
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": (
                    "Reviews the fix diff for correctness, edge cases, and code quality."
                ),
            },
            {
                "node": "approval_gate_pr",
                "label": "Approved for PR",
                "agent": "human",
                "description": "Human approval gate before raising a PR for the fix.",
            },
            {
                "node": "close",
                "label": "Raise PR",
                "agent": "system",
                "description": "Commits the fix, pushes to GitHub, and raises a pull request.",
            },
        ),
        tags=("bugfix", "hotfix"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="code_review",
        name="Code Review",
        description=("Automated code review pipeline: lint, security scan, review, feedback."),
        is_template=True,
        stage_names=(
            "lint",
            "security_scan",
            "review",
            "feedback",
        ),
        graph_nodes=(
            "lint",
            "security_scan",
            "review",
            "feedback",
        ),
        graph_edges=(
            ("lint", "security_scan"),
            ("security_scan", "review"),
            ("review", "feedback"),
        ),
        entry_point="lint",
        node_metadata=(
            {
                "node": "lint",
                "label": "Lint",
                "agent": "system",
                "description": (
                    "Runs linters and formatters to check code style and catch common issues."
                ),
            },
            {
                "node": "security_scan",
                "label": "Security Scan",
                "agent": "security",
                "agent_id": "agent_security",
                "description": (
                    "Scans for known vulnerabilities, insecure patterns, and dependency issues."
                ),
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": "Provides a detailed code review with suggestions for improvement.",
            },
            {
                "node": "feedback",
                "label": "Feedback",
                "agent": "system",
                "description": (
                    "Compiles lint, security, and review findings into a summary report."
                ),
            },
        ),
        tags=("review", "quality"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="refactor",
        name="Refactor",
        description=("Safe refactoring: research, plan, implement, test for regressions, review."),
        is_template=True,
        stage_names=(
            "research",
            "plan",
            "approve_spec",
            "refactor",
            "test",
            "review",
            "approved_for_pr",
            "raise_pr",
        ),
        graph_nodes=(
            "research",
            "plan",
            "approval_gate_spec",
            "refactor",
            "test",
            "review",
            "approval_gate_pr",
            "close",
        ),
        graph_edges=(
            ("research", "plan"),
            ("plan", "approval_gate_spec"),
            ("approval_gate_spec", "refactor"),
            ("refactor", "test"),
            ("test", "review"),
            ("review", "approval_gate_pr"),
            ("approval_gate_pr", "close"),
        ),
        entry_point="research",
        interrupt_before=(
            "approval_gate_spec",
            "approval_gate_pr",
        ),
        node_metadata=(
            {
                "node": "research",
                "label": "Research",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Researches the codebase to identify refactoring targets, code smells, and"
                    " improvement areas."
                ),
            },
            {
                "node": "plan",
                "label": "Plan",
                "agent": "planner",
                "agent_id": "agent_planner",
                "description": (
                    "Creates a structured refactoring plan with safe transformation steps."
                ),
            },
            {
                "node": "approval_gate_spec",
                "label": "Approve Spec",
                "agent": "human",
                "description": "Human reviews and approves the refactoring plan.",
            },
            {
                "node": "refactor",
                "label": "Refactor",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": "Applies the planned refactoring transformations to the codebase.",
            },
            {
                "node": "test",
                "label": "Test",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": (
                    "Runs the full test suite to ensure no regressions from the refactoring."
                ),
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": "Reviews the refactored code for quality and correctness.",
            },
            {
                "node": "approval_gate_pr",
                "label": "Approved for PR",
                "agent": "human",
                "description": "Human approval before raising a PR for the refactored code.",
            },
            {
                "node": "close",
                "label": "Raise PR",
                "agent": "system",
                "description": (
                    "Commits the refactoring, pushes to GitHub, and raises a pull request."
                ),
            },
        ),
        tags=("refactor", "tech-debt"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="security_audit",
        name="Security Audit",
        description=("Security-focused pipeline: dependency scan, code scan, report, remediate."),
        is_template=True,
        stage_names=(
            "dependency_scan",
            "code_scan",
            "secret_scan",
            "report",
            "approve_remediation",
            "remediate",
        ),
        graph_nodes=(
            "dependency_scan",
            "code_scan",
            "secret_scan",
            "report",
            "approval_gate",
            "remediate",
        ),
        graph_edges=(
            ("dependency_scan", "code_scan"),
            ("code_scan", "secret_scan"),
            ("secret_scan", "report"),
            ("report", "approval_gate"),
            ("approval_gate", "remediate"),
        ),
        entry_point="dependency_scan",
        interrupt_before=("approval_gate",),
        node_metadata=(
            {
                "node": "dependency_scan",
                "label": "Dependency Scan",
                "agent": "security",
                "agent_id": "agent_security",
                "description": "Scans project dependencies for known CVEs and outdated packages.",
            },
            {
                "node": "code_scan",
                "label": "Code Scan",
                "agent": "security",
                "agent_id": "agent_security",
                "description": (
                    "Static analysis for security vulnerabilities (OWASP Top 10, injection, XSS)."
                ),
            },
            {
                "node": "secret_scan",
                "label": "Secret Scan",
                "agent": "security",
                "agent_id": "agent_security",
                "description": (
                    "Detects hardcoded secrets, API keys, and credentials in the codebase."
                ),
            },
            {
                "node": "report",
                "label": "Report",
                "agent": "system",
                "description": "Compiles all scan findings into a prioritised security report.",
            },
            {
                "node": "approval_gate",
                "label": "Approve Remediation",
                "agent": "human",
                "description": "Human reviews the report and approves remediation actions.",
            },
            {
                "node": "remediate",
                "label": "Remediate",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": "Applies fixes for identified security vulnerabilities.",
            },
        ),
        tags=("security", "audit", "compliance"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="incident_response",
        name="Incident Response",
        description=("Incident workflow: triage, investigate, hotfix, deploy, post-mortem."),
        is_template=True,
        stage_names=(
            "triage",
            "investigate",
            "hotfix",
            "test",
            "approve_deploy",
            "deploy",
            "post_mortem",
        ),
        graph_nodes=(
            "triage",
            "investigate",
            "hotfix",
            "test",
            "approval_gate_deploy",
            "deploy",
            "post_mortem",
        ),
        graph_edges=(
            ("triage", "investigate"),
            ("investigate", "hotfix"),
            ("hotfix", "test"),
            ("test", "approval_gate_deploy"),
            ("approval_gate_deploy", "deploy"),
            ("deploy", "post_mortem"),
        ),
        entry_point="triage",
        interrupt_before=("approval_gate_deploy",),
        node_metadata=(
            {
                "node": "triage",
                "label": "Triage",
                "agent": "triage",
                "agent_id": "agent_triage",
                "description": (
                    "Assesses incident severity, identifies affected systems, and sets response"
                    " priority."
                ),
            },
            {
                "node": "investigate",
                "label": "Investigate",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Investigates root cause by analysing logs, metrics, and recent changes."
                ),
            },
            {
                "node": "hotfix",
                "label": "Hotfix",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": "Develops a minimal, targeted fix to resolve the incident.",
            },
            {
                "node": "test",
                "label": "Test",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": "Validates the hotfix doesn't introduce regressions.",
            },
            {
                "node": "approval_gate_deploy",
                "label": "Approve Deploy",
                "agent": "human",
                "description": "Human approval before deploying the hotfix to production.",
            },
            {
                "node": "deploy",
                "label": "Deploy",
                "agent": "devops",
                "agent_id": "agent_devops",
                "description": "Deploys the hotfix to the affected environment.",
            },
            {
                "node": "post_mortem",
                "label": "Post-Mortem",
                "agent": "tech_lead",
                "agent_id": "agent_tech_lead",
                "description": "Documents root cause, timeline, and preventive actions.",
            },
        ),
        tags=("incident", "hotfix", "on-call"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="documentation",
        name="Documentation",
        description=("Documentation pipeline: research code, draft docs, review, publish."),
        is_template=True,
        stage_names=(
            "research",
            "draft",
            "review",
            "publish",
        ),
        graph_nodes=(
            "research",
            "draft",
            "review",
            "publish",
        ),
        graph_edges=(
            ("research", "draft"),
            ("draft", "review"),
            ("review", "publish"),
        ),
        entry_point="research",
        node_metadata=(
            {
                "node": "research",
                "label": "Research",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Researches code structure, public APIs, and existing documentation gaps."
                ),
            },
            {
                "node": "draft",
                "label": "Draft Docs",
                "agent": "documentation",
                "agent_id": "agent_documentation",
                "description": (
                    "Generates documentation drafts covering APIs, architecture, and usage"
                    " examples."
                ),
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": "Reviews documentation for accuracy, completeness, and clarity.",
            },
            {
                "node": "publish",
                "label": "Publish",
                "agent": "system",
                "description": "Publishes the approved documentation to the configured output.",
            },
        ),
        tags=("documentation", "docs"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="release",
        name="Release",
        description=("Release pipeline: changelog, version bump, build, test, approve, deploy."),
        is_template=True,
        stage_names=(
            "changelog",
            "version_bump",
            "build",
            "test",
            "approve_release",
            "deploy",
            "notify",
        ),
        graph_nodes=(
            "changelog",
            "version_bump",
            "build",
            "test",
            "approval_gate_release",
            "deploy",
            "notify",
        ),
        graph_edges=(
            ("changelog", "version_bump"),
            ("version_bump", "build"),
            ("build", "test"),
            ("test", "approval_gate_release"),
            ("approval_gate_release", "deploy"),
            ("deploy", "notify"),
        ),
        entry_point="changelog",
        interrupt_before=("approval_gate_release",),
        node_metadata=(
            {
                "node": "changelog",
                "label": "Changelog",
                "agent": "documentation",
                "agent_id": "agent_documentation",
                "description": (
                    "Generates a changelog from commits and merged PRs since the last release."
                ),
            },
            {
                "node": "version_bump",
                "label": "Version Bump",
                "agent": "system",
                "description": (
                    "Bumps the version number according to semver based on change types."
                ),
            },
            {
                "node": "build",
                "label": "Build",
                "agent": "devops",
                "agent_id": "agent_devops",
                "description": "Builds release artefacts (packages, containers, binaries).",
            },
            {
                "node": "test",
                "label": "Test",
                "agent": "qa",
                "agent_id": "agent_qa",
                "description": "Runs the full test suite against the release build.",
            },
            {
                "node": "approval_gate_release",
                "label": "Approve Release",
                "agent": "human",
                "description": "Human approval before publishing the release.",
            },
            {
                "node": "deploy",
                "label": "Deploy",
                "agent": "devops",
                "agent_id": "agent_devops",
                "description": "Deploys the release to the target environment.",
            },
            {
                "node": "notify",
                "label": "Notify",
                "agent": "system",
                "description": "Sends release notifications to configured channels.",
            },
        ),
        tags=("release", "deployment"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="onboarding",
        name="Developer Onboarding",
        description=("Onboard a new developer: setup, codebase tour, first task, review."),
        is_template=True,
        stage_names=(
            "setup",
            "codebase_tour",
            "first_task",
            "review",
            "complete",
        ),
        graph_nodes=(
            "setup",
            "codebase_tour",
            "first_task",
            "review",
            "complete",
        ),
        graph_edges=(
            ("setup", "codebase_tour"),
            ("codebase_tour", "first_task"),
            ("first_task", "review"),
            ("review", "complete"),
        ),
        entry_point="setup",
        node_metadata=(
            {
                "node": "setup",
                "label": "Setup Environment",
                "agent": "devops",
                "agent_id": "agent_devops",
                "description": (
                    "Provisions the development environment with required tools and dependencies."
                ),
            },
            {
                "node": "codebase_tour",
                "label": "Codebase Tour",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Walks through the codebase architecture, key modules, and conventions."
                ),
            },
            {
                "node": "first_task",
                "label": "First Task",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": "Assigns and guides through a starter task to build familiarity.",
            },
            {
                "node": "review",
                "label": "Review",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": (
                    "Reviews the first task submission and provides constructive feedback."
                ),
            },
            {
                "node": "complete",
                "label": "Complete",
                "agent": "system",
                "description": "Marks onboarding as complete and records the developer's progress.",
            },
        ),
        tags=("onboarding", "developer-experience"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="spike",
        name="Technical Spike",
        description=("Time-boxed research spike: investigate, prototype, report findings."),
        is_template=True,
        stage_names=(
            "define_scope",
            "research",
            "prototype",
            "report",
        ),
        graph_nodes=(
            "define_scope",
            "research",
            "prototype",
            "report",
        ),
        graph_edges=(
            ("define_scope", "research"),
            ("research", "prototype"),
            ("prototype", "report"),
        ),
        entry_point="define_scope",
        node_metadata=(
            {
                "node": "define_scope",
                "label": "Define Scope",
                "agent": "tech_lead",
                "agent_id": "agent_tech_lead",
                "description": (
                    "Defines the research questions, constraints, and time box for the spike."
                ),
            },
            {
                "node": "research",
                "label": "Research",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Investigates technical options, reads documentation, and evaluates trade-offs."
                ),
            },
            {
                "node": "prototype",
                "label": "Prototype",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": "Builds a minimal proof-of-concept to validate the chosen approach.",
            },
            {
                "node": "report",
                "label": "Report",
                "agent": "documentation",
                "agent_id": "agent_documentation",
                "description": "Summarises findings, recommendations, and next steps.",
            },
        ),
        tags=("spike", "research", "investigation"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="extract_integration_patterns",
        name="Integration Analysis",
        description=(
            "Analyse a repository's integration patterns, service dependencies,"
            " and coupling scores."
        ),
        is_template=True,
        stage_names=(
            "ingest",
            "setup_workspace",
            "scan_repo",
            "classify_integrations",
            "build_graph",
            "detect_antipatterns",
            "persist_results",
        ),
        graph_nodes=(
            "ingest",
            "setup_workspace",
            "scan_repo",
            "classify_integrations",
            "build_graph",
            "detect_antipatterns",
            "persist_results",
            "error",
        ),
        graph_edges=(
            ("ingest", "setup_workspace"),
            ("setup_workspace", "scan_repo"),
            ("classify_integrations", "build_graph"),
            ("build_graph", "detect_antipatterns"),
            ("detect_antipatterns", "persist_results"),
        ),
        conditional_edges=(
            {
                "source": "scan_repo",
                "targets": {
                    "continue": "classify_integrations",
                    "error": "error",
                },
            },
        ),
        entry_point="ingest",
        node_metadata=(
            {
                "node": "ingest",
                "label": "Ingest",
                "agent": "system",
                "description": "Processes the incoming request and resolves trigger context.",
            },
            {
                "node": "setup_workspace",
                "label": "Setup Workspace",
                "agent": "system",
                "description": "Clones the repository into a sandbox for analysis.",
            },
            {
                "node": "scan_repo",
                "label": "Scan Repository",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Scans the repository for API endpoints, imports, and service boundaries."
                ),
            },
            {
                "node": "classify_integrations",
                "label": "Classify Integrations",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Classifies each integration by pattern (REST, gRPC, pub/sub, etc.)."
                ),
            },
            {
                "node": "build_graph",
                "label": "Build Graph",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": "Builds a service dependency graph with protocols and data flows.",
            },
            {
                "node": "detect_antipatterns",
                "label": "Detect Anti-patterns",
                "agent": "reviewer",
                "agent_id": "agent_reviewer",
                "description": "Flags coupling anti-patterns and architectural risks.",
            },
            {
                "node": "persist_results",
                "label": "Persist Results",
                "agent": "system",
                "description": "Saves the integration map, patterns, and coupling scores.",
            },
            {
                "node": "error",
                "label": "Error",
                "agent": "system",
                "description": "Handles errors from the scan phase.",
            },
        ),
        tags=("integration", "architecture", "analysis"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="process_mining",
        name="Process Mining",
        description=(
            "Discover and map data/process flows in a repository: HTTP request paths, "
            "event sourcing chains, command dispatch, background jobs, and external integrations. "
            "Produces individual Mermaid diagrams per flow type."
        ),
        is_template=True,
        stage_names=(
            "ingest",
            "setup_workspace",
            "discover_endpoints",
            "trace_flows",
            "classify_flows",
            "generate_diagrams",
            "persist_results",
        ),
        graph_nodes=(
            "ingest",
            "setup_workspace",
            "discover_endpoints",
            "trace_flows",
            "classify_flows",
            "generate_diagrams",
            "persist_results",
            "error",
        ),
        graph_edges=(
            ("ingest", "setup_workspace"),
            ("setup_workspace", "discover_endpoints"),
            ("trace_flows", "classify_flows"),
            ("classify_flows", "generate_diagrams"),
            ("generate_diagrams", "persist_results"),
        ),
        conditional_edges=(
            {
                "source": "discover_endpoints",
                "targets": {
                    "continue": "trace_flows",
                    "error": "error",
                },
            },
        ),
        entry_point="ingest",
        node_metadata=(
            {
                "node": "ingest",
                "label": "Ingest",
                "agent": "system",
                "description": "Processes the incoming request and resolves trigger context.",
            },
            {
                "node": "setup_workspace",
                "label": "Setup Workspace",
                "agent": "system",
                "description": "Clones the repository into a sandbox for analysis.",
            },
            {
                "node": "discover_endpoints",
                "label": "Discover Endpoints",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Scans source files for HTTP routes, event handlers, "
                    "command handlers, and background jobs."
                ),
            },
            {
                "node": "trace_flows",
                "label": "Trace Flows",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Traces each endpoint through middleware, services, stores, and sinks."
                ),
            },
            {
                "node": "classify_flows",
                "label": "Classify Flows",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Categorises flows by type: HTTP, event sourcing, "
                    "command dispatch, background, external."
                ),
            },
            {
                "node": "generate_diagrams",
                "label": "Generate Diagrams",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": ("Generates individual Mermaid sequence diagrams per flow type."),
            },
            {
                "node": "persist_results",
                "label": "Persist Results",
                "agent": "system",
                "description": "Saves flow maps, diagrams, and metrics to the store.",
            },
            {
                "node": "error",
                "label": "Error",
                "agent": "system",
                "description": "Handles errors from the discovery phase.",
            },
        ),
        tags=("process-mining", "data-flow", "analysis"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="regulation_to_policy",
        name="Regulation to Policy",
        description=(
            "Convert regulations into actionable policies and procedures: gather context, "
            "analyse regulation text, generate policies, approve, and finalise."
        ),
        is_template=True,
        stage_names=(
            "gather_context",
            "analyse_regulation",
            "generate_policies",
            "approval_gate_policies",
            "finalise",
        ),
        graph_nodes=(
            "gather_context",
            "analyse_regulation",
            "generate_policies",
            "approval_gate_policies",
            "finalise",
        ),
        graph_edges=(
            ("gather_context", "analyse_regulation"),
            ("analyse_regulation", "generate_policies"),
            ("generate_policies", "approval_gate_policies"),
            ("approval_gate_policies", "finalise"),
        ),
        entry_point="gather_context",
        interrupt_before=("approval_gate_policies",),
        node_metadata=(
            {
                "node": "gather_context",
                "label": "Gather Context",
                "agent": "researcher",
                "agent_id": "agent_researcher",
                "description": (
                    "Loads regulation text, project context, existing policies, "
                    "and industry-specific frameworks."
                ),
            },
            {
                "node": "analyse_regulation",
                "label": "Analyse Regulation",
                "agent": "architect",
                "agent_id": "agent_architect",
                "description": (
                    "Breaks down the regulation into key requirements, obligations, "
                    "and compliance criteria."
                ),
            },
            {
                "node": "generate_policies",
                "label": "Generate Policies",
                "agent": "coder",
                "agent_id": "agent_coder",
                "description": (
                    "Generates draft policies and procedures that address each "
                    "identified regulatory requirement."
                ),
            },
            {
                "node": "approval_gate_policies",
                "label": "Approve Policies",
                "agent": "human",
                "description": (
                    "Human reviews generated policies and procedures before finalisation."
                ),
            },
            {
                "node": "finalise",
                "label": "Finalise",
                "agent": "system",
                "description": (
                    "Persists approved policies and procedures, updates the compliance "
                    "store, and records audit trail."
                ),
            },
        ),
        tags=("compliance", "regulation", "policy-generation"),
        is_builtin=True,
    ),
)
