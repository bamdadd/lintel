"""Tests for pipeline pre-flight checks."""

from __future__ import annotations

from unittest.mock import AsyncMock

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
            sandbox_manager=AsyncMock(),
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
            sandbox_manager=AsyncMock(),
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


class TestCredentialCheck:
    async def test_missing_credential_fails(self) -> None:
        cred_store = AsyncMock()
        cred_store.get = AsyncMock(return_value=None)
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            credential_ids=("cred-missing",),
            credential_store=cred_store,
        )
        assert not result.passed
        assert any("cred-missing" in e for e in result.errors)

    async def test_existing_credential_passes(self) -> None:
        cred_store = AsyncMock()
        cred_store.get = AsyncMock(return_value={"credential_id": "c1"})
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            credential_ids=("c1",),
            credential_store=cred_store,
        )
        assert result.passed

    async def test_no_credential_ids_skips_check(self) -> None:
        cred_store = AsyncMock()
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            credential_ids=(),
            credential_store=cred_store,
        )
        assert result.passed
        cred_store.get.assert_not_called()

    async def test_no_credential_store_skips_check(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            credential_ids=("c1",),
            credential_store=None,
        )
        assert result.passed

    async def test_credential_store_error_treated_as_failure(self) -> None:
        cred_store = AsyncMock()
        cred_store.get = AsyncMock(side_effect=RuntimeError("db down"))
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            credential_ids=("c1",),
            credential_store=cred_store,
        )
        assert not result.passed
        assert any("unavailable" in e.lower() for e in result.errors)


class TestSandboxCheck:
    async def test_code_workflow_without_sandbox_warns(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            sandbox_manager=None,
        )
        assert result.passed
        assert any("sandbox" in w.lower() for w in result.warnings)

    async def test_code_workflow_with_sandbox_no_warning(self) -> None:
        result = await run_preflight_checks(
            workflow_type="feature_to_pr",
            repo_url="https://github.com/org/repo",
            project_id="proj-1",
            sandbox_manager=AsyncMock(),
        )
        sandbox_warnings = [w for w in result.warnings if "sandbox" in w.lower()]
        assert not sandbox_warnings

    async def test_non_code_workflow_without_sandbox_no_warning(self) -> None:
        result = await run_preflight_checks(
            workflow_type="review_only",
            project_id="proj-1",
            sandbox_manager=None,
        )
        sandbox_warnings = [w for w in result.warnings if "sandbox" in w.lower()]
        assert not sandbox_warnings
