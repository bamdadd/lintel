"""Tests for pipeline pre-flight checks."""

from __future__ import annotations

from lintel.pipelines_api.preflight import run_preflight_checks

# Workflows that require a repository URL
_CODE_WORKFLOWS = ["feature_to_pr", "bug_fix", "refactor"]
_NON_CODE_WORKFLOWS = ["review_only", "unknown_custom"]


class TestRepoUrlCheck:
    async def test_code_workflow_without_repo_fails(self) -> None:
        for wf in _CODE_WORKFLOWS:
            result = await run_preflight_checks(workflow_type=wf, repo_url="", repo_urls=())
            assert not result.passed, f"{wf} should fail without repo URL"
            assert any("repository" in e.lower() for e in result.errors)

    async def test_code_workflow_with_repo_url_passes(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
        )
        assert result.passed
        assert not result.errors

    async def test_code_workflow_with_repo_urls_passes(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="",
            repo_urls=("https://github.com/org/repo",),
        )
        assert result.passed

    async def test_non_code_workflow_without_repo_passes(self) -> None:
        result = await run_preflight_checks(
            workflow_type="review_only",
            repo_url="",
        )
        assert result.passed


class TestProjectIdCheck:
    async def test_empty_project_id_warns(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="",
        )
        assert result.passed
        assert any("project" in w.lower() for w in result.warnings)

    async def test_with_project_id_no_warning(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
        )
        assert not result.warnings


class TestMultipleErrors:
    async def test_collects_all_errors(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="",
            project_id="",
        )
        assert not result.passed
        assert len(result.errors) >= 1
        assert len(result.warnings) >= 1


class TestPreflightResult:
    async def test_passed_when_no_errors(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
        )
        assert result.passed
        assert not result.errors
        assert not result.warnings

    async def test_not_passed_when_errors(self) -> None:
        result = await run_preflight_checks(
            workflow_type="bug_fix",
            repo_url="",
        )
        assert not result.passed
