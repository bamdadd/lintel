"""Pipeline stage integration tests — each stage runs against a real sandbox.

Tests the full chain from research through PR creation using a fake
AgentRuntime that returns canned LLM responses, so we validate the
plumbing without spending tokens.

Run: pytest tests/integration/sandbox/test_pipeline_stages.py -v --run-sandbox
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.integration.sandbox.fake_runtime import (
    PLAN_RESPONSE,
    RESEARCH_REPORT,
    make_fake_runtime,
)

if TYPE_CHECKING:
    from lintel.agents.runtime import AgentRuntime
    from lintel.sandbox.protocols import SandboxManager

pytestmark = pytest.mark.usefixtures("_check_sandbox_prereqs")

FIXTURE_PROJECT = Path(__file__).parent.parent.parent / "fixtures" / "sample-python-project"
WORKDIR = "/workspace/repo"


# ---------------------------------------------------------------------------
# Tiny helper objects
# ---------------------------------------------------------------------------


class SandboxProject:
    """Wraps a sandbox with a fixture project loaded and git-initialised."""

    def __init__(self, mgr: SandboxManager, sandbox_id: str) -> None:
        self.mgr = mgr
        self.sandbox_id = sandbox_id

    async def setup(self) -> None:
        """Copy fixture project into sandbox and init git repo."""
        from lintel.sandbox.types import SandboxJob

        await self.mgr.execute(
            self.sandbox_id,
            SandboxJob(command=f"mkdir -p {WORKDIR}/src {WORKDIR}/tests", timeout_seconds=10),
        )
        for root, _dirs, files in os.walk(FIXTURE_PROJECT):
            for fname in files:
                local = Path(root) / fname
                remote = f"{WORKDIR}/{local.relative_to(FIXTURE_PROJECT)}"
                await self.mgr.write_file(self.sandbox_id, remote, local.read_text())

        await self.mgr.execute(
            self.sandbox_id,
            SandboxJob(
                command=(
                    "git init && git add -A"
                    " && git -c user.name=test -c user.email=test@test commit -m init"
                ),
                workdir=WORKDIR,
                timeout_seconds=30,
            ),
        )

    async def install_deps(self) -> None:
        """Install Python deps so tests can run."""
        from lintel.sandbox.types import SandboxJob

        await self.mgr.execute(
            self.sandbox_id,
            SandboxJob(
                command=(
                    'export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -3'
                ),
                workdir=WORKDIR,
                timeout_seconds=120,
            ),
        )

    async def cat(self, path: str) -> str:
        """Read a file from the sandbox."""
        from lintel.sandbox.types import SandboxJob

        r = await self.mgr.execute(
            self.sandbox_id,
            SandboxJob(command=f"cat {path}", timeout_seconds=10),
        )
        return r.stdout

    async def git_log(self) -> list[str]:
        """Return list of one-line commit messages."""
        from lintel.sandbox.types import SandboxJob

        r = await self.mgr.execute(
            self.sandbox_id,
            SandboxJob(command=f"cd {WORKDIR} && git log --oneline", timeout_seconds=10),
        )
        return [line for line in r.stdout.strip().split("\n") if line.strip()]


class StageRunner:
    """Encapsulates config and state for running workflow stages."""

    def __init__(
        self,
        project: SandboxProject,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.project = project
        self.runtime = runtime

    @property
    def config(self) -> dict:
        """RunnableConfig with services injected."""
        cfg: dict = {"sandbox_manager": self.project.mgr}
        if self.runtime:
            cfg["agent_runtime"] = self.runtime
        return {"configurable": cfg}

    def state(self, **overrides: object) -> dict:
        """Build a minimal ThreadWorkflowState dict."""
        base = {
            "thread_ref": "test:test:test",
            "correlation_id": "test-corr-id",
            "current_phase": "planning",
            "sanitized_messages": ["Add subtract and divide functions to math_utils"],
            "intent": "feature",
            "plan": {},
            "agent_outputs": [],
            "pending_approvals": [],
            "sandbox_id": self.project.sandbox_id,
            "sandbox_results": [],
            "pr_url": "",
            "error": "",
            "run_id": "",
            "work_item_id": "",
            "repo_url": "",
            "repo_branch": "main",
            "feature_branch": "lintel/feature/test",
            "workspace_path": WORKDIR,
            "research_context": "",
            "token_usage": [],
            "credential_ids": [],
            "review_cycles": 0,
        }
        base.update(overrides)
        return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(sandbox: tuple[SandboxManager, str]) -> SandboxProject:
    """Sandbox with fixture project loaded."""
    mgr, sandbox_id = sandbox
    proj = SandboxProject(mgr, sandbox_id)
    await proj.setup()
    return proj


@pytest.fixture
def runner(project: SandboxProject) -> StageRunner:
    """Stage runner with fake agent runtime."""
    runtime = make_fake_runtime(WORKDIR)
    return StageRunner(project, runtime)


# ---------------------------------------------------------------------------
# Stage 1: Research — given a prompt, produce a research report
# ---------------------------------------------------------------------------


async def test_research_produces_report(runner: StageRunner) -> None:
    """Research node should analyse the codebase and produce a markdown report."""
    from lintel.workflows.nodes.research import research_codebase

    result = await research_codebase(runner.state(), runner.config)

    assert result["current_phase"] == "planning"
    assert result["research_context"]
    assert "## Relevant Files" in result["research_context"]
    assert "## Recommendations" in result["research_context"]
    assert result["agent_outputs"][0]["node"] == "research"


# ---------------------------------------------------------------------------
# Stage 2: Plan — given research context, produce a structured plan
# ---------------------------------------------------------------------------


async def test_plan_from_research(runner: StageRunner) -> None:
    """Plan node should parse research and produce a structured task plan."""
    from lintel.workflows.nodes.plan import plan_work

    state = runner.state(research_context=RESEARCH_REPORT)
    result = await plan_work(state, runner.config)

    assert result["current_phase"] == "awaiting_spec_approval"
    assert "spec_approval" in result["pending_approvals"]

    plan = result["plan"]
    assert len(plan["tasks"]) >= 2
    assert plan.get("summary")
    for task in plan["tasks"]:
        assert "title" in task


# ---------------------------------------------------------------------------
# Stage 3: Implement — generate code, write files, run tests until green
# ---------------------------------------------------------------------------


async def test_implement_generates_and_tests(runner: StageRunner) -> None:
    """Implement node should generate code, write files, and run tests."""
    from lintel.workflows.nodes.implement import spawn_implementation

    await runner.project.install_deps()

    plan = json.loads(PLAN_RESPONSE)
    state = runner.state(plan=plan, research_context="Simple math utils project")
    result = await spawn_implementation(state, runner.config)

    # Implement now goes directly to reviewing (tests run internally)
    assert result["current_phase"] == "reviewing"
    assert len(result.get("sandbox_results", [])) > 0

    diff = result["sandbox_results"][0].get("content", "")
    assert "subtract" in diff
    assert "divide" in diff

    # Verify files actually written
    math_src = await runner.project.cat(f"{WORKDIR}/src/math_utils.py")
    assert "subtract" in math_src
    assert "divide" in math_src

    test_src = await runner.project.cat(f"{WORKDIR}/tests/test_math_utils.py")
    assert "test_subtract" in test_src
    assert "test_divide" in test_src

    # Verify test verdict is in agent_outputs
    test_outputs = [o for o in result["agent_outputs"] if o.get("node") == "test"]
    assert len(test_outputs) == 1
    assert test_outputs[0]["verdict"] == "passed"


# ---------------------------------------------------------------------------
# Stage 4: Review — given diffs, review should approve
# ---------------------------------------------------------------------------


async def test_review_approves_good_diff(runner: StageRunner) -> None:
    """Review node should approve well-structured code changes."""
    from lintel.workflows.nodes.implement import spawn_implementation
    from lintel.workflows.nodes.review import review_output

    await runner.project.install_deps()
    plan = json.loads(PLAN_RESPONSE)
    impl_result = await spawn_implementation(runner.state(plan=plan), runner.config)

    review_state = runner.state(
        sandbox_results=impl_result.get("sandbox_results", []),
    )
    result = await review_output(review_state, runner.config)

    assert result["current_phase"] == "awaiting_pr_approval"
    assert "pr_approval" in result["pending_approvals"]
    assert result["agent_outputs"][0]["verdict"] == "approve"


# ---------------------------------------------------------------------------
# Stage 5: Close — commit changes and verify git state
# ---------------------------------------------------------------------------


async def test_close_commits_changes(runner: StageRunner) -> None:
    """Close node should commit changes. No real push (no credentials)."""
    from lintel.workflows.nodes.close import close_workflow
    from lintel.workflows.nodes.implement import spawn_implementation

    await runner.project.install_deps()
    plan = json.loads(PLAN_RESPONSE)
    await spawn_implementation(runner.state(plan=plan), runner.config)

    no_llm = StageRunner(runner.project)
    close_state = no_llm.state(
        feature_branch="lintel/feature/test-subtract",
        repo_url="",
        plan=plan,
        agent_outputs=[
            {"node": "review", "verdict": "approve", "output": "LGTM"},
            {"node": "test", "verdict": "passed"},
        ],
    )
    result = await close_workflow(close_state, no_llm.config)

    assert result["current_phase"] == "closed"

    commits = await runner.project.git_log()
    assert len(commits) >= 2, f"Expected >=2 commits. Got: {commits}"


# ---------------------------------------------------------------------------
# Stage 6: Close with PR — verify PR creation via injected repo_provider
# ---------------------------------------------------------------------------


async def test_close_creates_pr(runner: StageRunner) -> None:
    """Close node should create a PR and post the review comment."""
    from lintel.workflows.nodes.close import close_workflow
    from lintel.workflows.nodes.implement import spawn_implementation
    from tests.integration.sandbox.fake_runtime import FakeRepoProvider

    await runner.project.install_deps()
    plan = json.loads(PLAN_RESPONSE)
    await spawn_implementation(runner.state(plan=plan), runner.config)

    fake_repo = FakeRepoProvider()
    config = {
        "configurable": {
            "sandbox_manager": runner.project.mgr,
            "repo_provider": fake_repo,
        },
    }
    close_state = runner.state(
        feature_branch="lintel/feature/test-subtract",
        repo_url="https://github.com/test/sample-project",
        plan=plan,
        agent_outputs=[
            {"node": "review", "verdict": "approve", "output": "VERDICT: APPROVE\nLGTM"},
            {"node": "test", "verdict": "passed"},
        ],
    )

    # Push will fail (no real remote) but PR creation uses the fake provider
    result = await close_workflow(close_state, config)

    assert result["current_phase"] == "closed"

    # If push failed, PR won't be created — that's expected without a real remote.
    # But let's verify the commit was made regardless.
    commits = await runner.project.git_log()
    assert len(commits) >= 2


async def test_close_creates_pr_with_local_remote(runner: StageRunner) -> None:
    """Close node should create a PR when push succeeds (using a local bare repo)."""
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes.close import close_workflow
    from lintel.workflows.nodes.implement import spawn_implementation
    from tests.integration.sandbox.fake_runtime import FakeRepoProvider

    await runner.project.install_deps()
    plan = json.loads(PLAN_RESPONSE)
    await spawn_implementation(runner.state(plan=plan), runner.config)

    # Create a local bare repo as the "remote" so push succeeds
    mgr = runner.project.mgr
    sid = runner.project.sandbox_id
    await mgr.execute(
        sid,
        SandboxJob(
            command="git init --bare /tmp/remote.git",
            timeout_seconds=10,
        ),
    )
    await mgr.execute(
        sid,
        SandboxJob(
            command=(
                f"cd {WORKDIR} && git remote remove origin 2>/dev/null;"
                " git remote add origin /tmp/remote.git"
                " && git push -u origin main 2>/dev/null || true"
            ),
            timeout_seconds=15,
        ),
    )
    # Create the feature branch so close_workflow can push it
    await mgr.execute(
        sid,
        SandboxJob(
            command=f"cd {WORKDIR} && git checkout -b lintel/feature/test-subtract",
            timeout_seconds=10,
        ),
    )

    fake_repo = FakeRepoProvider(
        pr_url="https://github.com/test/sample-project/pull/99",
    )
    config = {
        "configurable": {
            "sandbox_manager": mgr,
            "repo_provider": fake_repo,
        },
    }
    close_state = runner.state(
        feature_branch="lintel/feature/test-subtract",
        repo_url="https://github.com/test/sample-project",
        plan=plan,
        agent_outputs=[
            {"node": "review", "verdict": "approve", "output": "VERDICT: APPROVE\nLGTM"},
            {"node": "test", "verdict": "passed"},
        ],
    )

    result = await close_workflow(close_state, config)

    assert result["current_phase"] == "closed"
    assert result["pr_url"] == "https://github.com/test/sample-project/pull/99"

    # Verify the fake provider was called correctly
    assert len(fake_repo.created_prs) == 1
    pr = fake_repo.created_prs[0]
    assert pr["head"] == "lintel/feature/test-subtract"
    assert pr["base"] == "main"
    assert pr["repo_url"] == "https://github.com/test/sample-project"
    assert "subtract" in pr["body"].lower() or "Changes" in pr["body"]

    # Verify review comment was posted
    assert len(fake_repo.comments) == 1
    assert fake_repo.comments[0]["pr_number"] == 99
    assert "APPROVE" in fake_repo.comments[0]["body"]


# ---------------------------------------------------------------------------
# End-to-end: research -> plan -> implement (with tests) -> review -> close
# ---------------------------------------------------------------------------


async def test_full_pipeline(runner: StageRunner) -> None:
    """All stages sequentially — validates the full pipeline plumbing."""
    from lintel.workflows.nodes.close import close_workflow
    from lintel.workflows.nodes.implement import spawn_implementation
    from lintel.workflows.nodes.plan import plan_work
    from lintel.workflows.nodes.research import research_codebase
    from lintel.workflows.nodes.review import review_output

    await runner.project.install_deps()
    no_llm = StageRunner(runner.project)

    # 1. Research
    research = await research_codebase(runner.state(), runner.config)
    assert research["research_context"]

    # 2. Plan
    plan_result = await plan_work(
        runner.state(research_context=research["research_context"]),
        runner.config,
    )
    plan = plan_result["plan"]
    assert len(plan["tasks"]) >= 2

    # 3. Implement (now includes testing internally)
    impl = await spawn_implementation(runner.state(plan=plan), runner.config)
    assert impl["current_phase"] == "reviewing"

    # 4. Review
    review = await review_output(
        runner.state(sandbox_results=impl.get("sandbox_results", [])),
        runner.config,
    )
    assert review["agent_outputs"][0]["verdict"] == "approve"

    # 5. Close
    close = await close_workflow(
        no_llm.state(
            plan=plan,
            repo_url="",
            agent_outputs=[
                {"node": "review", "verdict": "approve", "output": "LGTM"},
                {"node": "test", "verdict": "passed"},
            ],
        ),
        no_llm.config,
    )
    assert close["current_phase"] == "closed"
    assert len(await runner.project.git_log()) >= 2
