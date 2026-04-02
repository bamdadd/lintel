"""Tests for CI webhook parser."""

from lintel.domain.cicd.parser import CIWebhookParser
from lintel.domain.cicd.types import CIBuildStatus, CIProvider, CIWebhookPayload

parser = CIWebhookParser()


def test_parse_github_actions_success() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GITHUB_ACTIONS,
        body={
            "workflow_run": {
                "id": 12345,
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "head_sha": "abc123",
                "name": "CI",
                "html_url": "https://github.com/org/repo/actions/runs/12345",
                "head_repository": {"html_url": "https://github.com/org/repo"},
            },
        },
    )
    build = parser.parse(payload)
    assert build.build_id == "12345"
    assert build.provider == CIProvider.GITHUB_ACTIONS
    assert build.status == CIBuildStatus.SUCCESS
    assert build.branch == "main"
    assert build.commit_sha == "abc123"
    assert build.pipeline_name == "CI"
    assert build.repo_url == "https://github.com/org/repo"


def test_parse_github_actions_in_progress() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GITHUB_ACTIONS,
        body={
            "workflow_run": {
                "id": 999,
                "status": "in_progress",
                "conclusion": "",
                "head_branch": "feat/x",
                "head_sha": "def456",
                "name": "Build",
                "html_url": "",
                "head_repository": {"html_url": ""},
            },
        },
    )
    build = parser.parse(payload)
    assert build.status == CIBuildStatus.RUNNING


def test_parse_github_actions_failure() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GITHUB_ACTIONS,
        body={
            "workflow_run": {
                "id": 111,
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "fff",
                "name": "CI",
                "html_url": "",
                "head_repository": {"html_url": ""},
            },
        },
    )
    build = parser.parse(payload)
    assert build.status == CIBuildStatus.FAILURE


def test_parse_concourse() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.CONCOURSE,
        body={
            "build_id": "42",
            "status": "succeeded",
            "repo_url": "https://github.com/org/repo",
            "branch": "develop",
            "commit_sha": "aaa111",
            "pipeline_name": "deploy",
            "build_url": "https://concourse.example.com/builds/42",
        },
    )
    build = parser.parse(payload)
    assert build.build_id == "42"
    assert build.provider == CIProvider.CONCOURSE
    assert build.status == CIBuildStatus.SUCCESS
    assert build.branch == "develop"
    assert build.pipeline_name == "deploy"


def test_parse_concourse_aborted() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.CONCOURSE,
        body={
            "build_id": "99",
            "status": "aborted",
            "repo_url": "",
            "branch": "",
            "commit_sha": "",
        },
    )
    build = parser.parse(payload)
    assert build.status == CIBuildStatus.CANCELLED


def test_parse_generic_webhook() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GENERIC_WEBHOOK,
        body={
            "build_id": "ext-1",
            "status": "success",
            "repo_url": "https://gitlab.com/org/repo",
            "branch": "main",
            "commit_sha": "bbb222",
        },
    )
    build = parser.parse(payload)
    assert build.build_id == "ext-1"
    assert build.provider == CIProvider.GENERIC_WEBHOOK
    assert build.status == CIBuildStatus.SUCCESS


def test_parse_generic_unknown_status() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GENERIC_WEBHOOK,
        body={"build_id": "x", "status": "weird", "repo_url": "", "branch": "", "commit_sha": ""},
    )
    build = parser.parse(payload)
    assert build.status == CIBuildStatus.UNKNOWN


def test_parse_github_actions_with_timestamps() -> None:
    payload = CIWebhookPayload(
        provider=CIProvider.GITHUB_ACTIONS,
        body={
            "workflow_run": {
                "id": 1,
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "head_sha": "sha",
                "name": "CI",
                "html_url": "",
                "head_repository": {"html_url": ""},
                "run_started_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-15T10:05:00Z",
            },
        },
    )
    build = parser.parse(payload)
    assert build.started_at is not None
    assert build.finished_at is not None
