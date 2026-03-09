"""Skill: discover how to run tests for a project.

Inspects the project structure inside a sandbox and returns the command(s)
needed to run the test suite.  Projects can register a custom version of
this skill (same skill_id, higher version) to override the default
discovery logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager

from lintel.contracts.types import (
    SkillDescriptor,
    SkillExecutionMode,
    SkillResult,
)

logger = logging.getLogger(__name__)

SKILL_ID = "skill_discover_test_command"


@dataclass(frozen=True)
class DiscoverTestCommandSkill:
    """Concrete implementation of the test-discovery skill.

    Inspects a sandbox workspace and returns:
    - ``test_command``: the shell command to run the tests
    - ``setup_commands``: optional list of commands to run first (dep install, etc.)
    """

    @property
    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            name=SKILL_ID,
            version="1.0.0",
            description="Discover how to run the test suite for any project.",
            input_schema={
                "type": "object",
                "properties": {
                    "workdir": {
                        "type": "string",
                        "description": "Workspace path inside the sandbox",
                    },
                    "sandbox_id": {"type": "string"},
                },
                "required": ["workdir", "sandbox_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "test_command": {"type": "string"},
                    "setup_commands": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["test_command"],
            },
            execution_mode=SkillExecutionMode.SANDBOX,
            allowed_agent_roles=frozenset({"qa_engineer", "coder", "devops"}),
        )

    async def execute(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        """Discover the test command by inspecting the project."""
        sandbox_manager: SandboxManager | None = context.get("sandbox_manager")
        sandbox_id: str = inputs.get("sandbox_id", "")
        workdir: str = inputs.get("workdir", "/workspace/repo")

        if not sandbox_manager or not sandbox_id:
            return SkillResult(
                success=False,
                error="sandbox_manager and sandbox_id are required in context/inputs",
            )

        result = await discover_test_command(sandbox_manager, sandbox_id, workdir)
        return SkillResult(success=True, output=result)


async def discover_test_command(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> dict[str, Any]:
    """Inspect a project and return the test command and setup commands.

    Strategy (priority order):
    1. Makefile with a test-like target → ``make <target>``
    2. package.json with a ``test`` script → ``npm test``
    3. pyproject.toml → ``uv run python -m pytest``
    4. Cargo.toml → ``cargo test``
    5. go.mod → ``go test ./...``
    6. Fallback → echo message

    Returns a dict with ``test_command`` (str) and ``setup_commands`` (list[str]).
    """
    from lintel.contracts.types import SandboxJob

    setup_commands: list[str] = []

    # Check what files exist in the project root
    detect = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                f"ls {workdir}/Makefile {workdir}/pyproject.toml "
                f"{workdir}/package.json {workdir}/Cargo.toml {workdir}/go.mod "
                "2>/dev/null || true"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    files = detect.stdout.strip()

    # 1. Makefile — parse targets for test-related ones
    if "Makefile" in files:
        test_target = await _find_make_test_target(sandbox_manager, sandbox_id, workdir)
        if test_target:
            # If the project also has pyproject.toml, ensure deps are ready
            if "pyproject.toml" in files:
                setup_commands = _python_setup_commands(workdir)
            return {
                "test_command": f"make {test_target}",
                "setup_commands": setup_commands,
            }

    # 2. package.json — check for test script
    if "package.json" in files:
        has_test = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(f"grep -q '\"test\"' {workdir}/package.json && echo HAS_TEST || true"),
                workdir=workdir,
                timeout_seconds=5,
            ),
        )
        if "HAS_TEST" in has_test.stdout:
            return {"test_command": "npm test", "setup_commands": ["npm install"]}

    # 3. pyproject.toml — Python project
    if "pyproject.toml" in files:
        setup_commands = _python_setup_commands(workdir)
        return {
            "test_command": ('export PATH="$HOME/.local/bin:$PATH" && uv run python -m pytest'),
            "setup_commands": setup_commands,
        }

    # 4. Cargo.toml
    if "Cargo.toml" in files:
        return {"test_command": "cargo test", "setup_commands": []}

    # 5. go.mod
    if "go.mod" in files:
        return {"test_command": "go test ./...", "setup_commands": []}

    return {"test_command": "echo 'No test runner detected'", "setup_commands": []}


def _python_setup_commands(workdir: str) -> list[str]:
    """Return setup commands for a Python project using uv."""
    return [
        'export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -5',
    ]


async def _find_make_test_target(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> str | None:
    """Parse Makefile for a test-related target, preferring ``make help`` output."""
    from lintel.contracts.types import SandboxJob

    # Try `make help` first
    help_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="make help 2>/dev/null || true",
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    if help_result.stdout.strip():
        target = pick_test_target(help_result.stdout)
        if target:
            return target

    # Fallback: parse Makefile target names directly
    targets_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                f"grep -E '^[a-zA-Z_-]+:' {workdir}/Makefile "
                "| sed 's/:.*//' | sort -u 2>/dev/null || true"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    if targets_result.stdout.strip():
        return pick_test_target(targets_result.stdout)

    return None


def pick_test_target(output: str) -> str | None:
    """Pick the best test target from make help or target list output.

    Only matches the first token on each line (the target name).
    Priority: 'test' > 'test-all' > 'all' > 'check' > 'test-unit' > 'verify'
    """
    targets: set[str] = set()
    for line in output.lower().strip().split("\n"):
        tokens = line.split()
        if tokens:
            targets.add(tokens[0])

    preferred = ("test", "test-all", "all", "check", "test-unit", "verify")
    for candidate in preferred:
        if candidate in targets:
            return candidate
    return None
