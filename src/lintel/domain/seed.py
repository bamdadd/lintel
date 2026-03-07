"""Default seed data for agents, skills, and workflow definitions.

All seed data uses the domain types from contracts.types so that refactors
to the schema are caught by the type checker and mypy.
"""

from __future__ import annotations

from lintel.contracts.types import (
    AgentCategory,
    AgentDefinitionRecord,
    AgentRole,
    SkillCategory,
    SkillDefinition,
    SkillExecutionMode,
    WorkflowDefinitionRecord,
)

# ---------------------------------------------------------------------------
# Default agent definitions — one per engineering team role
# ---------------------------------------------------------------------------

DEFAULT_AGENTS: tuple[AgentDefinitionRecord, ...] = (
    AgentDefinitionRecord(
        agent_id="agent_planner",
        name="Planner",
        role=AgentRole.PLANNER,
        category=AgentCategory.ENGINEERING,
        description=(
            "Breaks down feature requests into actionable "
            "plans with tasks, dependencies, and criteria."
        ),
        system_prompt=(
            "You are a senior software planner. Given a feature "
            "request or bug report, produce a detailed plan with "
            "numbered tasks, complexity, dependencies, and criteria."
        ),
        is_builtin=True,
        tags=("planning", "decomposition"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_architect",
        name="Architect",
        role=AgentRole.ARCHITECT,
        category=AgentCategory.ENGINEERING,
        description=(
            "Designs system architecture, evaluates trade-offs, "
            "and produces technical design documents."
        ),
        system_prompt=(
            "You are a software architect. Analyse requirements "
            "and produce architecture designs including component "
            "diagrams, data flow, API contracts, database schema "
            "changes, and trade-off analysis."
        ),
        is_builtin=True,
        tags=("architecture", "design", "technical-design"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_coder",
        name="Coder",
        role=AgentRole.CODER,
        category=AgentCategory.ENGINEERING,
        description=(
            "Implements code changes following the plan "
            "and architecture decisions."
        ),
        system_prompt=(
            "You are a senior software engineer. Implement code "
            "changes following the provided plan. Write clean, "
            "well-tested code. Prefer small, focused commits."
        ),
        is_builtin=True,
        tags=("implementation", "coding"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_reviewer",
        name="Code Reviewer",
        role=AgentRole.REVIEWER,
        category=AgentCategory.QUALITY,
        description=(
            "Reviews code changes for correctness, style, "
            "security, and performance."
        ),
        system_prompt=(
            "You are a thorough code reviewer. Examine changes "
            "for bugs, security issues, performance problems, "
            "style violations, and plan adherence. "
            "Provide actionable feedback with line references."
        ),
        is_builtin=True,
        tags=("review", "quality"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_qa",
        name="QA Engineer",
        role=AgentRole.QA_ENGINEER,
        category=AgentCategory.QUALITY,
        description=(
            "Writes and runs tests, validates acceptance "
            "criteria, and reports quality metrics."
        ),
        system_prompt=(
            "You are a QA engineer. Write comprehensive test "
            "cases covering unit, integration, and edge-case "
            "scenarios. Validate acceptance criteria. "
            "Report test coverage and quality metrics."
        ),
        is_builtin=True,
        tags=("testing", "quality-assurance"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_devops",
        name="DevOps Engineer",
        role=AgentRole.DEVOPS,
        category=AgentCategory.OPERATIONS,
        description=(
            "Manages CI/CD pipelines, infrastructure changes, "
            "and deployment configurations."
        ),
        system_prompt=(
            "You are a DevOps engineer. Handle CI/CD config, "
            "Dockerfile updates, IaC changes, deployment scripts, "
            "and environment configuration. "
            "Follow infrastructure best practices."
        ),
        is_builtin=True,
        tags=("devops", "ci-cd", "infrastructure"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_security",
        name="Security Analyst",
        role=AgentRole.SECURITY,
        category=AgentCategory.QUALITY,
        description=(
            "Performs security reviews, identifies "
            "vulnerabilities, and suggests mitigations."
        ),
        system_prompt=(
            "You are a security analyst. Review code and configs "
            "for OWASP Top 10 vulnerabilities, dependency risks, "
            "secret exposure, and access control issues. "
            "Provide severity ratings and remediation steps."
        ),
        is_builtin=True,
        tags=("security", "vulnerability-analysis"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_tech_lead",
        name="Tech Lead",
        role=AgentRole.TECH_LEAD,
        category=AgentCategory.LEADERSHIP,
        description=(
            "Orchestrates the team, resolves conflicts, "
            "makes technical decisions, ensures delivery."
        ),
        system_prompt=(
            "You are a tech lead. Coordinate between agents, "
            "resolve conflicting recommendations, make final "
            "technical decisions, and ensure delivery stays "
            "on track. Escalate blockers."
        ),
        is_builtin=True,
        tags=("leadership", "coordination"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_pm",
        name="Product Manager",
        role=AgentRole.PM,
        category=AgentCategory.LEADERSHIP,
        description=(
            "Clarifies requirements, prioritises work, "
            "and communicates status to stakeholders."
        ),
        system_prompt=(
            "You are a product manager. Clarify ambiguous "
            "requirements by asking targeted questions. "
            "Prioritise work items, track progress, "
            "and produce status summaries."
        ),
        is_builtin=True,
        tags=("product", "requirements", "communication"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_documentation",
        name="Documentation Writer",
        role=AgentRole.DOCUMENTATION,
        category=AgentCategory.COMMUNICATION,
        description=(
            "Writes and updates technical documentation, "
            "READMEs, API docs, and changelogs."
        ),
        system_prompt=(
            "You are a technical writer. Produce clear, "
            "concise documentation including README updates, "
            "API reference docs, ADRs, changelogs, "
            "and inline code comments where needed."
        ),
        is_builtin=True,
        tags=("documentation", "writing"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_triage",
        name="Triage Bot",
        role=AgentRole.TRIAGE,
        category=AgentCategory.OPERATIONS,
        description=(
            "Classifies incoming issues, assigns priority "
            "and labels, and routes to the right team."
        ),
        system_prompt=(
            "You are a triage bot. Classify incoming issues "
            "by type (bug, feature, question, task), assign "
            "severity/priority, add labels, and route to "
            "the appropriate agent or team member."
        ),
        is_builtin=True,
        tags=("triage", "classification"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_designer",
        name="UI/UX Designer",
        role=AgentRole.DESIGNER,
        category=AgentCategory.DESIGN,
        description=(
            "Creates UI mockups, reviews UX flows, "
            "and ensures design consistency."
        ),
        system_prompt=(
            "You are a UI/UX designer. Create wireframes and "
            "UI specifications, review user flows for usability, "
            "and ensure design consistency with the project's "
            "design system."
        ),
        is_builtin=True,
        tags=("design", "ux", "ui"),
    ),
    AgentDefinitionRecord(
        agent_id="agent_summarizer",
        name="Summarizer",
        role=AgentRole.SUMMARIZER,
        category=AgentCategory.COMMUNICATION,
        description=(
            "Summarises long threads, meetings, and "
            "discussions into concise actionable notes."
        ),
        system_prompt=(
            "You are a summariser. Condense long conversations, "
            "PR threads, and meeting notes into concise, "
            "actionable summaries with key decisions, "
            "action items, and open questions."
        ),
        is_builtin=True,
        tags=("summarization", "communication"),
    ),
)

# ---------------------------------------------------------------------------
# Default skills — engineering team capabilities
# ---------------------------------------------------------------------------

DEFAULT_SKILLS: tuple[SkillDefinition, ...] = (
    # --- Code Generation ---
    SkillDefinition(
        skill_id="skill_write_code",
        name="Write Code",
        version="1.0.0",
        description=(
            "Generate code in any language following "
            "project conventions and the plan."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Generate clean, well-structured code "
            "following the project's conventions."
        ),
        allowed_agent_roles=(
            AgentRole.CODER,
            AgentRole.ARCHITECT,
            AgentRole.TECH_LEAD,
        ),
        tags=("code", "generation"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_refactor",
        name="Refactor Code",
        version="1.0.0",
        description=(
            "Restructure existing code to improve "
            "readability or performance without "
            "changing behavior."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Refactor the provided code preserving all "
            "existing behavior while improving structure."
        ),
        allowed_agent_roles=(
            AgentRole.CODER,
            AgentRole.ARCHITECT,
            AgentRole.REVIEWER,
        ),
        tags=("refactor", "code-quality"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_fix_bug",
        name="Fix Bug",
        version="1.0.0",
        description=(
            "Diagnose and fix a reported bug with "
            "root cause analysis and regression test."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Diagnose the bug, identify root cause, "
            "apply a minimal fix, and add a regression test."
        ),
        allowed_agent_roles=(AgentRole.CODER, AgentRole.QA_ENGINEER),
        tags=("bugfix", "debugging"),
        is_builtin=True,
    ),
    # --- Code Analysis ---
    SkillDefinition(
        skill_id="skill_code_review",
        name="Code Review",
        version="1.0.0",
        description=(
            "Review a diff or set of files for "
            "correctness, style, and best practices."
        ),
        category=SkillCategory.CODE_ANALYSIS,
        system_prompt=(
            "Review the code changes. Check for bugs, "
            "style issues, security problems, "
            "and suggest improvements."
        ),
        allowed_agent_roles=(
            AgentRole.REVIEWER,
            AgentRole.TECH_LEAD,
            AgentRole.SECURITY,
        ),
        tags=("review", "analysis"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_explain_code",
        name="Explain Code",
        version="1.0.0",
        description=(
            "Explain what a piece of code does, its "
            "design rationale, and potential issues."
        ),
        category=SkillCategory.CODE_ANALYSIS,
        system_prompt=(
            "Explain the provided code clearly, covering "
            "purpose, design decisions, and potential issues."
        ),
        allowed_agent_roles=(
            AgentRole.CODER,
            AgentRole.REVIEWER,
            AgentRole.DOCUMENTATION,
            AgentRole.TECH_LEAD,
            AgentRole.SUMMARIZER,
        ),
        tags=("explanation", "understanding"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_dependency_analysis",
        name="Dependency Analysis",
        version="1.0.0",
        description=(
            "Analyse project dependencies for "
            "vulnerabilities, updates, and compatibility."
        ),
        category=SkillCategory.CODE_ANALYSIS,
        system_prompt=(
            "Analyse dependencies for known vulnerabilities, "
            "available updates, and compatibility risks."
        ),
        allowed_agent_roles=(
            AgentRole.SECURITY,
            AgentRole.DEVOPS,
            AgentRole.TECH_LEAD,
        ),
        tags=("dependencies", "supply-chain"),
        is_builtin=True,
    ),
    # --- Testing ---
    SkillDefinition(
        skill_id="skill_write_tests",
        name="Write Tests",
        version="1.0.0",
        description=(
            "Generate unit, integration, or e2e tests "
            "for the specified code."
        ),
        category=SkillCategory.TESTING,
        system_prompt=(
            "Write comprehensive tests covering happy path, "
            "edge cases, and error scenarios."
        ),
        allowed_agent_roles=(AgentRole.QA_ENGINEER, AgentRole.CODER),
        tags=("testing", "unit-tests", "integration-tests"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_run_tests",
        name="Run Tests",
        version="1.0.0",
        description="Execute the project test suite and report results.",
        category=SkillCategory.TESTING,
        execution_mode=SkillExecutionMode.SANDBOX,
        system_prompt=(
            "Run the test suite and report pass/fail counts, "
            "coverage, and failure details."
        ),
        allowed_agent_roles=(
            AgentRole.QA_ENGINEER,
            AgentRole.CODER,
            AgentRole.DEVOPS,
        ),
        tags=("testing", "execution"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_generate_test_data",
        name="Generate Test Data",
        version="1.0.0",
        description=(
            "Generate realistic test fixtures and seed data "
            "for development and testing."
        ),
        category=SkillCategory.TESTING,
        system_prompt=(
            "Generate realistic test data matching "
            "the specified schema and constraints."
        ),
        allowed_agent_roles=(AgentRole.QA_ENGINEER, AgentRole.CODER),
        tags=("testing", "fixtures", "seed-data"),
        is_builtin=True,
    ),
    # --- Documentation ---
    SkillDefinition(
        skill_id="skill_write_docs",
        name="Write Documentation",
        version="1.0.0",
        description=(
            "Write or update technical documentation, "
            "READMEs, and API reference."
        ),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=(
            "Write clear, concise documentation following "
            "the project's documentation standards."
        ),
        allowed_agent_roles=(
            AgentRole.DOCUMENTATION,
            AgentRole.CODER,
            AgentRole.ARCHITECT,
        ),
        tags=("documentation", "readme"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_adr",
        name="Write ADR",
        version="1.0.0",
        description=(
            "Write an Architecture Decision Record capturing "
            "context, decision, and consequences."
        ),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=(
            "Write an ADR with status, context, decision, "
            "and consequences sections."
        ),
        allowed_agent_roles=(
            AgentRole.ARCHITECT,
            AgentRole.TECH_LEAD,
            AgentRole.DOCUMENTATION,
        ),
        tags=("adr", "architecture", "decisions"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_changelog",
        name="Write Changelog",
        version="1.0.0",
        description=(
            "Generate a changelog entry from commits "
            "and PR descriptions."
        ),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=(
            "Generate a changelog entry following "
            "Keep a Changelog format."
        ),
        allowed_agent_roles=(
            AgentRole.DOCUMENTATION,
            AgentRole.PM,
            AgentRole.SUMMARIZER,
        ),
        tags=("changelog", "release-notes"),
        is_builtin=True,
    ),
    # --- DevOps ---
    SkillDefinition(
        skill_id="skill_write_dockerfile",
        name="Write Dockerfile",
        version="1.0.0",
        description=(
            "Create or update Dockerfiles and "
            "docker-compose configurations."
        ),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write optimised, secure Dockerfiles following "
            "multi-stage build best practices."
        ),
        allowed_agent_roles=(AgentRole.DEVOPS, AgentRole.CODER),
        tags=("docker", "containerisation"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_ci_config",
        name="Write CI/CD Config",
        version="1.0.0",
        description=(
            "Create or update CI/CD pipeline configuration "
            "(GitHub Actions, etc.)."
        ),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write CI/CD configuration that is efficient, "
            "secure, and follows best practices."
        ),
        allowed_agent_roles=(AgentRole.DEVOPS, AgentRole.TECH_LEAD),
        tags=("ci-cd", "github-actions", "pipeline"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_iac",
        name="Write Infrastructure as Code",
        version="1.0.0",
        description=(
            "Create or update Terraform, CloudFormation, "
            "or other IaC configurations."
        ),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write infrastructure-as-code following "
            "least privilege and immutable infra patterns."
        ),
        allowed_agent_roles=(AgentRole.DEVOPS,),
        tags=("terraform", "infrastructure", "iac"),
        is_builtin=True,
    ),
    # --- Security ---
    SkillDefinition(
        skill_id="skill_security_scan",
        name="Security Scan",
        version="1.0.0",
        description=(
            "Scan code for OWASP Top 10 vulnerabilities "
            "and common security anti-patterns."
        ),
        category=SkillCategory.SECURITY,
        system_prompt=(
            "Scan the code for security vulnerabilities. "
            "Report severity, location, and remediation."
        ),
        allowed_agent_roles=(AgentRole.SECURITY, AgentRole.REVIEWER),
        tags=("security", "owasp", "vulnerability"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_secret_detection",
        name="Secret Detection",
        version="1.0.0",
        description=(
            "Detect hardcoded secrets, API keys, "
            "and credentials in code."
        ),
        category=SkillCategory.SECURITY,
        system_prompt=(
            "Scan for hardcoded secrets, API keys, "
            "passwords, and tokens. Flag all findings."
        ),
        allowed_agent_roles=(
            AgentRole.SECURITY,
            AgentRole.REVIEWER,
            AgentRole.DEVOPS,
        ),
        tags=("secrets", "credentials", "detection"),
        is_builtin=True,
    ),
    # --- Project Management ---
    SkillDefinition(
        skill_id="skill_estimate",
        name="Estimate Work",
        version="1.0.0",
        description=(
            "Estimate complexity and effort "
            "for a set of tasks."
        ),
        category=SkillCategory.PROJECT_MANAGEMENT,
        system_prompt=(
            "Estimate the complexity and effort for each "
            "task. Use t-shirt sizing (S/M/L/XL)."
        ),
        allowed_agent_roles=(
            AgentRole.PM,
            AgentRole.TECH_LEAD,
            AgentRole.PLANNER,
        ),
        tags=("estimation", "planning"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_triage_issue",
        name="Triage Issue",
        version="1.0.0",
        description=(
            "Classify, prioritise, and label an "
            "incoming issue or request."
        ),
        category=SkillCategory.PROJECT_MANAGEMENT,
        system_prompt=(
            "Classify the issue type, assign priority "
            "(P0-P3), add labels, suggest assignee role."
        ),
        allowed_agent_roles=(AgentRole.TRIAGE, AgentRole.PM),
        tags=("triage", "classification", "prioritisation"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_summarise_thread",
        name="Summarise Thread",
        version="1.0.0",
        description=(
            "Summarise a conversation thread into key "
            "decisions, actions, and open questions."
        ),
        category=SkillCategory.COMMUNICATION,
        system_prompt=(
            "Summarise the thread concisely: key decisions, "
            "action items, and open questions."
        ),
        allowed_agent_roles=(
            AgentRole.SUMMARIZER,
            AgentRole.PM,
            AgentRole.TECH_LEAD,
        ),
        tags=("summary", "communication"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_create_pr",
        name="Create Pull Request",
        version="1.0.0",
        description=(
            "Create a well-structured PR with title, "
            "description, and linked issues."
        ),
        category=SkillCategory.CODE_GENERATION,
        execution_mode=SkillExecutionMode.SANDBOX,
        system_prompt=(
            "Create a PR with a clear title, structured "
            "description, and linked work items."
        ),
        allowed_agent_roles=(AgentRole.CODER, AgentRole.TECH_LEAD),
        tags=("git", "pull-request"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_database_migration",
        name="Write Database Migration",
        version="1.0.0",
        description=(
            "Generate database migration scripts "
            "for schema changes."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Generate a safe, reversible database migration "
            "script for the requested schema change."
        ),
        allowed_agent_roles=(
            AgentRole.CODER,
            AgentRole.ARCHITECT,
            AgentRole.DEVOPS,
        ),
        tags=("database", "migration", "schema"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_performance_analysis",
        name="Performance Analysis",
        version="1.0.0",
        description=(
            "Analyse code for performance bottlenecks "
            "and suggest optimisations."
        ),
        category=SkillCategory.CODE_ANALYSIS,
        system_prompt=(
            "Identify performance bottlenecks, suggest "
            "optimisations, and estimate impact."
        ),
        allowed_agent_roles=(
            AgentRole.REVIEWER,
            AgentRole.ARCHITECT,
            AgentRole.TECH_LEAD,
        ),
        tags=("performance", "optimisation"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_api_design",
        name="Design API",
        version="1.0.0",
        description=(
            "Design RESTful or GraphQL API endpoints "
            "with schemas and error handling."
        ),
        category=SkillCategory.DESIGN,
        system_prompt=(
            "Design API endpoints following REST best "
            "practices with clear request/response schemas."
        ),
        allowed_agent_roles=(
            AgentRole.ARCHITECT,
            AgentRole.CODER,
            AgentRole.TECH_LEAD,
        ),
        tags=("api", "design", "rest"),
        is_builtin=True,
    ),
)

# ---------------------------------------------------------------------------
# Default workflow definitions — engineering team pipelines
# ---------------------------------------------------------------------------

DEFAULT_WORKFLOW_DEFINITIONS: tuple[WorkflowDefinitionRecord, ...] = (
    WorkflowDefinitionRecord(
        definition_id="feature_to_pr",
        name="Feature to PR",
        description=(
            "End-to-end feature implementation: "
            "plan, implement, test, review, merge."
        ),
        is_template=True,
        stage_names=(
            "ingest", "route", "plan", "approve_spec",
            "implement", "test", "review",
            "approve_merge", "merge",
        ),
        graph_nodes=(
            "ingest", "route", "plan",
            "approval_gate_spec", "implement", "test",
            "review", "approval_gate_merge", "close",
        ),
        graph_edges=(
            ("ingest", "route"),
            ("plan", "approval_gate_spec"),
            ("approval_gate_spec", "implement"),
            ("implement", "test"),
            ("test", "review"),
            ("review", "approval_gate_merge"),
            ("approval_gate_merge", "close"),
        ),
        conditional_edges=(
            {
                "source": "route",
                "targets": {"plan": "plan", "close": "close"},
            },
        ),
        entry_point="ingest",
        interrupt_before=(
            "approval_gate_spec",
            "approval_gate_merge",
        ),
        tags=("feature", "full-pipeline"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="bug_fix",
        name="Bug Fix",
        description=(
            "Triage, reproduce, fix, test, "
            "and review a bug report."
        ),
        is_template=True,
        stage_names=(
            "triage", "reproduce", "fix", "test",
            "review", "approve_merge", "merge",
        ),
        graph_nodes=(
            "triage", "reproduce", "fix", "test",
            "review", "approval_gate_merge", "close",
        ),
        graph_edges=(
            ("triage", "reproduce"),
            ("reproduce", "fix"),
            ("fix", "test"),
            ("test", "review"),
            ("review", "approval_gate_merge"),
            ("approval_gate_merge", "close"),
        ),
        entry_point="triage",
        interrupt_before=("approval_gate_merge",),
        tags=("bugfix", "hotfix"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="code_review",
        name="Code Review",
        description=(
            "Automated code review pipeline: "
            "lint, security scan, review, feedback."
        ),
        is_template=True,
        stage_names=(
            "lint", "security_scan", "review", "feedback",
        ),
        graph_nodes=(
            "lint", "security_scan", "review", "feedback",
        ),
        graph_edges=(
            ("lint", "security_scan"),
            ("security_scan", "review"),
            ("review", "feedback"),
        ),
        entry_point="lint",
        tags=("review", "quality"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="refactor",
        name="Refactor",
        description=(
            "Safe refactoring: analyse, plan, implement, "
            "test for regressions, review."
        ),
        is_template=True,
        stage_names=(
            "analyse", "plan", "approve_spec", "refactor",
            "test", "review", "approve_merge", "merge",
        ),
        graph_nodes=(
            "analyse", "plan", "approval_gate_spec",
            "refactor", "test", "review",
            "approval_gate_merge", "close",
        ),
        graph_edges=(
            ("analyse", "plan"),
            ("plan", "approval_gate_spec"),
            ("approval_gate_spec", "refactor"),
            ("refactor", "test"),
            ("test", "review"),
            ("review", "approval_gate_merge"),
            ("approval_gate_merge", "close"),
        ),
        entry_point="analyse",
        interrupt_before=(
            "approval_gate_spec",
            "approval_gate_merge",
        ),
        tags=("refactor", "tech-debt"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="security_audit",
        name="Security Audit",
        description=(
            "Security-focused pipeline: dependency scan, "
            "code scan, report, remediate."
        ),
        is_template=True,
        stage_names=(
            "dependency_scan", "code_scan", "secret_scan",
            "report", "approve_remediation", "remediate",
        ),
        graph_nodes=(
            "dependency_scan", "code_scan", "secret_scan",
            "report", "approval_gate", "remediate",
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
        tags=("security", "audit", "compliance"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="incident_response",
        name="Incident Response",
        description=(
            "Incident workflow: triage, investigate, "
            "hotfix, deploy, post-mortem."
        ),
        is_template=True,
        stage_names=(
            "triage", "investigate", "hotfix", "test",
            "approve_deploy", "deploy", "post_mortem",
        ),
        graph_nodes=(
            "triage", "investigate", "hotfix", "test",
            "approval_gate_deploy", "deploy", "post_mortem",
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
        tags=("incident", "hotfix", "on-call"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="documentation",
        name="Documentation",
        description=(
            "Documentation pipeline: analyse code, "
            "draft docs, review, publish."
        ),
        is_template=True,
        stage_names=(
            "analyse", "draft", "review", "publish",
        ),
        graph_nodes=(
            "analyse", "draft", "review", "publish",
        ),
        graph_edges=(
            ("analyse", "draft"),
            ("draft", "review"),
            ("review", "publish"),
        ),
        entry_point="analyse",
        tags=("documentation", "docs"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="release",
        name="Release",
        description=(
            "Release pipeline: changelog, version bump, "
            "build, test, approve, deploy."
        ),
        is_template=True,
        stage_names=(
            "changelog", "version_bump", "build", "test",
            "approve_release", "deploy", "notify",
        ),
        graph_nodes=(
            "changelog", "version_bump", "build", "test",
            "approval_gate_release", "deploy", "notify",
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
        tags=("release", "deployment"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="onboarding",
        name="Developer Onboarding",
        description=(
            "Onboard a new developer: setup, "
            "codebase tour, first task, review."
        ),
        is_template=True,
        stage_names=(
            "setup", "codebase_tour",
            "first_task", "review", "complete",
        ),
        graph_nodes=(
            "setup", "codebase_tour",
            "first_task", "review", "complete",
        ),
        graph_edges=(
            ("setup", "codebase_tour"),
            ("codebase_tour", "first_task"),
            ("first_task", "review"),
            ("review", "complete"),
        ),
        entry_point="setup",
        tags=("onboarding", "developer-experience"),
        is_builtin=True,
    ),
    WorkflowDefinitionRecord(
        definition_id="spike",
        name="Technical Spike",
        description=(
            "Time-boxed research spike: investigate, "
            "prototype, report findings."
        ),
        is_template=True,
        stage_names=(
            "define_scope", "research",
            "prototype", "report",
        ),
        graph_nodes=(
            "define_scope", "research",
            "prototype", "report",
        ),
        graph_edges=(
            ("define_scope", "research"),
            ("research", "prototype"),
            ("prototype", "report"),
        ),
        entry_point="define_scope",
        tags=("spike", "research", "investigation"),
        is_builtin=True,
    ),
)
