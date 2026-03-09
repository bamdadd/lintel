"""Skill: discover how to run tests for a project.

Inspects the project structure inside a sandbox and returns the command(s)
needed to run the test suite, including all dependency setup.  Projects can
register a custom version of this skill (same skill_id, higher version) to
override the default discovery logic.
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
    - ``setup_commands``: ordered list of commands to prepare the environment
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

    Discovery strategy:
    1. Detect project files (Makefile, pyproject.toml, package.json, etc.)
    2. Detect available services in the sandbox (postgres, redis, etc.)
    3. Build setup commands for installing dependencies
    4. Choose the best test command, scoped to what's feasible in the sandbox

    Returns ``{"test_command": str, "setup_commands": list[str]}``.
    """
    from lintel.contracts.types import SandboxJob

    # --- Phase 1: Detect project files ---
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

    # --- Phase 2: Detect sandbox capabilities ---
    capabilities = await _detect_sandbox_capabilities(
        sandbox_manager,
        sandbox_id,
        workdir,
    )

    # --- Phase 3: Build setup + test command per project type ---

    # Python project
    if "pyproject.toml" in files:
        setup = await _python_setup_commands(
            sandbox_manager,
            sandbox_id,
            workdir,
        )
        test_cmd = await _python_test_command(
            sandbox_manager,
            sandbox_id,
            workdir,
            files,
            capabilities,
        )
        return {"test_command": test_cmd, "setup_commands": setup}

    # Node project
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
            return {
                "test_command": "npm test",
                "setup_commands": ["npm install"],
            }

    # Rust project
    if "Cargo.toml" in files:
        return {"test_command": "cargo test", "setup_commands": []}

    # Go project
    if "go.mod" in files:
        return {"test_command": "go test ./...", "setup_commands": []}

    return {
        "test_command": "echo 'No test runner detected'",
        "setup_commands": [],
    }


async def _detect_sandbox_capabilities(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> dict[str, bool]:
    """Probe which services/tools are available in the sandbox."""
    from lintel.contracts.types import SandboxJob

    probe = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "("
                "which pg_isready >/dev/null 2>&1 && pg_isready -q 2>/dev/null"
                ' && echo "HAS_POSTGRES"; '
                "which redis-cli >/dev/null 2>&1 && redis-cli ping 2>/dev/null"
                ' | grep -q PONG && echo "HAS_REDIS"; '
                'which docker >/dev/null 2>&1 && echo "HAS_DOCKER"; '
                'which uv >/dev/null 2>&1 && echo "HAS_UV"; '
                'which node >/dev/null 2>&1 && echo "HAS_NODE"; '
                "true"
                ")"
            ),
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    out = probe.stdout
    return {
        "postgres": "HAS_POSTGRES" in out,
        "redis": "HAS_REDIS" in out,
        "docker": "HAS_DOCKER" in out,
        "uv": "HAS_UV" in out,
        "node": "HAS_NODE" in out,
    }


async def _python_setup_commands(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> list[str]:
    """Build the full list of setup commands for a Python project."""
    from lintel.contracts.types import SandboxJob

    commands: list[str] = []
    path_prefix = 'export PATH="$HOME/.local/bin:$PATH"'

    # 1. Ensure uv is available
    check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="which uv 2>/dev/null || echo MISSING",
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    if "MISSING" in check.stdout:
        commands.append("curl -LsSf https://astral.sh/uv/install.sh | sh")

    # 2. Install project dependencies
    commands.append(f"{path_prefix} && uv sync --all-extras 2>&1 | tail -5")

    # 3. Detect extra Python dependencies from pyproject.toml
    extras = await _detect_python_extras(
        sandbox_manager,
        sandbox_id,
        workdir,
    )
    for cmd in extras:
        commands.append(cmd)

    return commands


async def _detect_python_extras(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> list[str]:
    """Scan pyproject.toml for dependencies that need post-install setup.

    Currently detects:
    - spacy → download en_core_web_sm model
    - nltk → download popular datasets
    """
    from lintel.contracts.types import SandboxJob

    commands: list[str] = []
    path_prefix = 'export PATH="$HOME/.local/bin:$PATH"'

    # Read dependency names from pyproject.toml
    deps_result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                f"grep -iE '\"(spacy|nltk|presidio)' {workdir}/pyproject.toml 2>/dev/null || true"
            ),
            workdir=workdir,
            timeout_seconds=5,
        ),
    )
    dep_lines = deps_result.stdout.lower()

    if "spacy" in dep_lines or "presidio" in dep_lines:
        commands.append(
            f"{path_prefix} && uv run python -m spacy download en_core_web_sm 2>&1 | tail -3"
        )

    if "nltk" in dep_lines:
        commands.append(
            f"{path_prefix} && uv run python -c "
            "\"import nltk; nltk.download('punkt'); nltk.download('stopwords')\" "
            "2>&1 | tail -3"
        )

    return commands


async def _python_test_command(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    files: str,
    capabilities: dict[str, bool],
) -> str:
    """Determine the best test command for a Python project.

    Priority:
    1. Makefile with test-like target (prefer test-unit in sandbox without DB)
    2. pytest directly
    """
    path_prefix = 'export PATH="$HOME/.local/bin:$PATH"'

    # Check Makefile targets
    if "Makefile" in files:
        test_target = await _find_make_test_target(
            sandbox_manager,
            sandbox_id,
            workdir,
        )
        if test_target:
            # In sandbox without postgres, prefer unit-only target
            if not capabilities.get("postgres"):
                unit_target = await _find_make_unit_target(
                    sandbox_manager,
                    sandbox_id,
                    workdir,
                )
                if unit_target:
                    logger.info(
                        "test_discovery: no postgres, using %s instead of %s",
                        unit_target,
                        test_target,
                    )
                    return f"make {unit_target}"
            return f"make {test_target}"

    # Fallback: run pytest directly, unit tests only if no DB
    if not capabilities.get("postgres"):
        return f"{path_prefix} && uv run python -m pytest tests/unit/ -v 2>&1 || true"
    return f"{path_prefix} && uv run python -m pytest"


async def _find_make_test_target(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> str | None:
    """Parse Makefile for a test-related target, preferring ``make help``."""
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


async def _find_make_unit_target(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
) -> str | None:
    """Find a unit-test-only Makefile target."""
    from lintel.contracts.types import SandboxJob

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
    if not targets_result.stdout.strip():
        return None

    targets: set[str] = set()
    for line in targets_result.stdout.lower().strip().split("\n"):
        tokens = line.split()
        if tokens:
            targets.add(tokens[0])

    # Prefer unit-only targets
    for candidate in ("test-unit", "test-units", "unit-test", "unittest"):
        if candidate in targets:
            return candidate
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
