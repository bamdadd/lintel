"""Gather codebase context from a sandbox for use in planning prompts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.protocols import SandboxManager
    from lintel.contracts.types import SandboxResult

logger = logging.getLogger(__name__)

# Files that are typically useful for understanding a project
CONTEXT_FILES = (
    "README.md",
    "README.rst",
    "README",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    "CLAUDE.md",
)

# Max characters per file to include in the prompt
MAX_FILE_CHARS = 3000

# Max total characters for all codebase context
MAX_TOTAL_CHARS = 15000


async def _run(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    command: str,
    workdir: str = "/",
    timeout: int = 15,
) -> str:
    """Run a command in the sandbox and return stdout, or empty string on failure."""
    from lintel.contracts.types import SandboxJob

    try:
        result: SandboxResult = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=command, workdir=workdir, timeout_seconds=timeout),
        )
        return result.stdout.strip()
    except Exception:
        return ""


async def gather_codebase_context(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    repo_path: str = "/workspace/repo",
) -> str:
    """Read directory structure and key files from the sandbox.

    Uses tree/ls for structure, grep for key patterns, and reads important files.
    Returns a formatted string suitable for inclusion in a planner prompt.
    """
    # Verify the repo path exists before gathering context
    repo_check = await _run(
        sandbox_manager, sandbox_id, f"test -d {repo_path} && echo EXISTS", workdir="/"
    )
    if "EXISTS" not in repo_check:
        logger.error(
            "codebase_context_repo_not_found repo_path=%s sandbox_id=%s",
            repo_path,
            sandbox_id,
        )
        msg = (
            f"Repository not found at {repo_path} in sandbox "
            f"{sandbox_id[:12]} — was the clone successful?"
        )
        raise FileNotFoundError(msg)

    sections: list[str] = []
    total_chars = 0

    def _add(section: str) -> bool:
        nonlocal total_chars
        if total_chars + len(section) > MAX_TOTAL_CHARS:
            return False
        sections.append(section)
        total_chars += len(section)
        return True

    # 1. Directory tree — try `tree` first, fall back to `ls -R`
    tree = await _run(
        sandbox_manager,
        sandbox_id,
        f"tree -L 3 -I 'node_modules|__pycache__|.venv|venv|.git|dist|build|.tox|*.pyc' "
        f"--dirsfirst {repo_path}",
    )
    if not tree:
        tree = await _run(
            sandbox_manager,
            sandbox_id,
            f"ls -R {repo_path} | head -150",
        )
    if tree:
        _add(f"## Directory Structure\n```\n{tree}\n```")

    # 2. Read key project files
    for filename in CONTEXT_FILES:
        if total_chars >= MAX_TOTAL_CHARS:
            break
        try:
            content = await sandbox_manager.read_file(sandbox_id, f"{repo_path}/{filename}")
            if content:
                truncated = content[:MAX_FILE_CHARS]
                if len(content) > MAX_FILE_CHARS:
                    truncated += "\n... (truncated)"
                _add(f"## {filename}\n```\n{truncated}\n```")
        except Exception:
            continue

    # 3. Grep for key patterns — entry points, exports, main functions
    patterns = [
        (
            "Entry points & main",
            r"def main\|if __name__\|func main\|fn main\|module\.exports\|export default",
        ),
        (
            "API routes & endpoints",
            r"@app\.\|@router\.\|app\.get\|app\.post\|@api_view\|@GetMapping\|@PostMapping",
        ),
        ("Class definitions", r"^class "),
    ]
    for label, pattern in patterns:
        if total_chars >= MAX_TOTAL_CHARS:
            break
        grep_out = await _run(
            sandbox_manager,
            sandbox_id,
            f"grep -rn '{pattern}' {repo_path} "
            f"--include='*.py' --include='*.ts' --include='*.js' "
            f"--include='*.go' --include='*.rs' --include='*.java' | head -40",
        )
        if grep_out:
            # Make paths relative
            grep_out = grep_out.replace(f"{repo_path}/", "")
            _add(f"## {label}\n```\n{grep_out}\n```")

    if not sections:
        return ""

    return "# Codebase Context\n\n" + "\n\n".join(sections)
