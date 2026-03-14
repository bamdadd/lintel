"""Shared fixtures for sandbox integration tests.

These tests require Docker and the lintel-sandbox image.
Run with: pytest tests/integration/sandbox/ -v --run-sandbox
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.contracts.protocols import SandboxManager


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-sandbox",
        action="store_true",
        default=False,
        help="Run sandbox integration tests (requires Docker + lintel-sandbox image)",
    )


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _sandbox_image_exists() -> bool:
    import subprocess

    result = subprocess.run(
        ["docker", "image", "inspect", "lintel-sandbox:latest"],
        capture_output=True,
    )
    return result.returncode == 0


@pytest.fixture(scope="session")
def _check_sandbox_prereqs(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--run-sandbox"):
        pytest.skip("sandbox tests disabled (use --run-sandbox)")
    if not _docker_available():
        pytest.skip("Docker not available")
    if not _sandbox_image_exists():
        pytest.skip("lintel-sandbox:latest image not built (run: make sandbox-image)")


@pytest.fixture
async def sandbox(
    _check_sandbox_prereqs: None,
) -> AsyncIterator[tuple[SandboxManager, str]]:
    """Create a real sandbox container and tear it down after the test."""
    from lintel.contracts.types import SandboxConfig, ThreadRef
    from lintel.sandbox.docker_backend import DockerSandboxManager

    mgr = DockerSandboxManager()
    config = SandboxConfig(network_enabled=True)
    thread_ref = ThreadRef(
        workspace_id="test",
        channel_id="test",
        thread_ts="test",
    )
    sandbox_id = await mgr.create(config, thread_ref)
    try:
        yield mgr, sandbox_id
    finally:
        await mgr.destroy(sandbox_id)


FIXTURE_PROJECT_PATH = "tests/fixtures/sample-python-project"
