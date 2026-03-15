"""Default skill definitions — engineering team capabilities."""

from __future__ import annotations

from lintel.agents.types import (
    AgentRole,
    SkillCategory,
    SkillDefinition,
    SkillExecutionMode,
)

DEFAULT_SKILLS: tuple[SkillDefinition, ...] = (
    # --- Code Generation ---
    SkillDefinition(
        skill_id="skill_write_code",
        name="Write Code",
        version="2.0.0",
        description=(
            "Implement features using strict TDD (red-green-refactor) with small, "
            "incremental steps. Tests and lint run continuously, not just at the end."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "You are a senior software engineer implementing a feature using strict TDD "
            "(Test-Driven Development) with small, incremental steps.\n\n"
            "## Process — Red / Green / Refactor\n\n"
            "Work in SMALL increments. Each increment is one logical unit of change "
            "(one function, one class, one endpoint, one entity). Never make large "
            "chunky changes — break the plan into the smallest possible steps.\n\n"
            "For EACH increment:\n\n"
            "1. **RED** — Write a failing test FIRST.\n"
            "   - The test should define the expected behaviour for the next small piece.\n"
            "   - Run the test suite to confirm the new test fails "
            "(and all existing tests still pass).\n"
            "   - Command: `{test_command}`\n\n"
            "2. **GREEN** — Write the MINIMAL production code to make the test pass.\n"
            "   - Do not write more code than needed to pass the test.\n"
            "   - Run the test suite to confirm all tests pass.\n"
            "   - Run the linter: `{lint_command}`\n"
            "   - Fix any lint errors immediately.\n\n"
            "3. **REFACTOR** — Clean up while tests are green.\n"
            "   - Remove duplication, improve naming, extract helpers.\n"
            "   - Run tests again to confirm nothing broke.\n"
            '   - Commit this increment: `git add -A && git commit -m "<description>"`\n\n'
            "## Rules\n\n"
            "- **Use Pydantic models** (BaseModel with frozen=True) for any new data "
            "structures, not plain dicts or untyped dataclasses. Follow the project's "
            "existing patterns.\n"
            "- **Never skip tests.** Every piece of production code must be covered by "
            "a test written BEFORE the implementation.\n"
            "- **Run tests and lint after EVERY file change**, not just at the end. If "
            "something breaks, fix it immediately before moving on.\n"
            "- **Commit after each green-refactor cycle.** Small commits are better "
            "than one big commit.\n"
            "- **Match the existing code style** — indentation, naming conventions, "
            "import style, module structure. Read existing files before writing new ones.\n"
            "- **Introduce entities incrementally.** If a feature needs a new entity, "
            "first add the entity type + a test for it, then the store, then the API "
            "endpoint — each as a separate red-green-refactor cycle.\n"
            "- **Existing tests must never break.** If you change a shared interface, "
            "update all callers and their tests in the same increment.\n"
            "- **Do not refactor unrelated code.** Only touch files relevant to the "
            "current task.\n"
            "- If the project uses frozen dataclasses (as in contracts/types.py), follow "
            "that pattern for domain types. Use Pydantic BaseModel for API request/"
            "response schemas.\n\n"
            "## Lint & Type Check\n"
            "- Lint: `{lint_command}`\n"
            "- Type check: `{typecheck_command}` (run periodically, not after every change)\n\n"
            "## Test Execution\n"
            "- Full suite: `{test_command}`\n"
            "- Single file: `{test_single_command}`\n"
        ),
        execution_mode=SkillExecutionMode.SANDBOX,
        allowed_agent_roles=(
            AgentRole.CODER,
            AgentRole.ARCHITECT,
            AgentRole.TECH_LEAD,
        ),
        tags=("code", "generation", "tdd"),
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
            "Refactor the provided code preserving all existing behavior while improving structure."
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
            "Diagnose and fix a reported bug with root cause analysis and regression test."
        ),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Diagnose the bug, identify root cause, apply a minimal fix, and add a regression test."
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
        description=("Review a diff or set of files for correctness, style, and best practices."),
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
            "Explain what a piece of code does, its design rationale, and potential issues."
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
            "Analyse project dependencies for vulnerabilities, updates, and compatibility."
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
        description=("Generate unit, integration, or e2e tests for the specified code."),
        category=SkillCategory.TESTING,
        system_prompt=(
            "Write comprehensive tests covering happy path, edge cases, and error scenarios."
        ),
        allowed_agent_roles=(AgentRole.QA_ENGINEER, AgentRole.CODER),
        tags=("testing", "unit-tests", "integration-tests"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_discover_test_command",
        name="Discover Test Command",
        version="1.0.0",
        description=(
            "Inspect a project's structure to discover how to run its test suite. "
            "Checks Makefile targets (via make help), package.json scripts, "
            "pyproject.toml, Cargo.toml, and go.mod. Projects can register a "
            "custom version of this skill to override the default discovery."
        ),
        category=SkillCategory.TESTING,
        execution_mode=SkillExecutionMode.SANDBOX,
        system_prompt=(
            "Inspect the project workspace and determine the correct command to "
            "run the test suite. Prefer Makefile targets (check `make help` first). "
            "Return a JSON object with `test_command` (str) and `setup_commands` "
            "(list of shell commands to run before tests, e.g. dep installation)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "workdir": {"type": "string"},
                "sandbox_id": {"type": "string"},
            },
            "required": ["workdir", "sandbox_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "test_command": {"type": "string"},
                "setup_commands": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["test_command"],
        },
        allowed_agent_roles=(
            AgentRole.QA_ENGINEER,
            AgentRole.CODER,
            AgentRole.DEVOPS,
        ),
        tags=("testing", "discovery", "project-detection"),
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
            "Run the test suite and report pass/fail counts, coverage, and failure details."
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
        description=("Generate realistic test fixtures and seed data for development and testing."),
        category=SkillCategory.TESTING,
        system_prompt=(
            "Generate realistic test data matching the specified schema and constraints."
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
        description=("Write or update technical documentation, READMEs, and API reference."),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=(
            "Write clear, concise documentation following the project's documentation standards."
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
            "Write an Architecture Decision Record capturing context, decision, and consequences."
        ),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=("Write an ADR with status, context, decision, and consequences sections."),
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
        description=("Generate a changelog entry from commits and PR descriptions."),
        category=SkillCategory.DOCUMENTATION,
        system_prompt=("Generate a changelog entry following Keep a Changelog format."),
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
        description=("Create or update Dockerfiles and docker-compose configurations."),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write optimised, secure Dockerfiles following multi-stage build best practices."
        ),
        allowed_agent_roles=(AgentRole.DEVOPS, AgentRole.CODER),
        tags=("docker", "containerisation"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_ci_config",
        name="Write CI/CD Config",
        version="1.0.0",
        description=("Create or update CI/CD pipeline configuration (GitHub Actions, etc.)."),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write CI/CD configuration that is efficient, secure, and follows best practices."
        ),
        allowed_agent_roles=(AgentRole.DEVOPS, AgentRole.TECH_LEAD),
        tags=("ci-cd", "github-actions", "pipeline"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_write_iac",
        name="Write Infrastructure as Code",
        version="1.0.0",
        description=("Create or update Terraform, CloudFormation, or other IaC configurations."),
        category=SkillCategory.DEVOPS,
        system_prompt=(
            "Write infrastructure-as-code following least privilege and immutable infra patterns."
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
            "Scan code for OWASP Top 10 vulnerabilities and common security anti-patterns."
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
        description=("Detect hardcoded secrets, API keys, and credentials in code."),
        category=SkillCategory.SECURITY,
        system_prompt=(
            "Scan for hardcoded secrets, API keys, passwords, and tokens. Flag all findings."
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
        description=("Estimate complexity and effort for a set of tasks."),
        category=SkillCategory.PROJECT_MANAGEMENT,
        system_prompt=(
            "Estimate the complexity and effort for each task. Use t-shirt sizing (S/M/L/XL)."
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
        description=("Classify, prioritise, and label an incoming issue or request."),
        category=SkillCategory.PROJECT_MANAGEMENT,
        system_prompt=(
            "Classify the issue type, assign priority (P0-P3), add labels, suggest assignee role."
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
            "Summarise a conversation thread into key decisions, actions, and open questions."
        ),
        category=SkillCategory.COMMUNICATION,
        system_prompt=(
            "Summarise the thread concisely: key decisions, action items, and open questions."
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
        description=("Create a well-structured PR with title, description, and linked issues."),
        category=SkillCategory.CODE_GENERATION,
        execution_mode=SkillExecutionMode.SANDBOX,
        system_prompt=(
            "Create a PR with a clear title, structured description, and linked work items."
        ),
        allowed_agent_roles=(AgentRole.CODER, AgentRole.TECH_LEAD),
        tags=("git", "pull-request"),
        is_builtin=True,
    ),
    SkillDefinition(
        skill_id="skill_database_migration",
        name="Write Database Migration",
        version="1.0.0",
        description=("Generate database migration scripts for schema changes."),
        category=SkillCategory.CODE_GENERATION,
        system_prompt=(
            "Generate a safe, reversible database migration script for the requested schema change."
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
        description=("Analyse code for performance bottlenecks and suggest optimisations."),
        category=SkillCategory.CODE_ANALYSIS,
        system_prompt=(
            "Identify performance bottlenecks, suggest optimisations, and estimate impact."
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
        description=("Design RESTful or GraphQL API endpoints with schemas and error handling."),
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
