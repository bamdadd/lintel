"""Tests for CI/CD domain types."""

from lintel.domain.cicd.types import CIBuild, CIBuildStatus, CIProvider, CIWebhookPayload


def test_ci_provider_values() -> None:
    assert CIProvider.GITHUB_ACTIONS == "github_actions"
    assert CIProvider.CONCOURSE == "concourse"
    assert CIProvider.GENERIC_WEBHOOK == "generic_webhook"


def test_ci_build_status_values() -> None:
    assert CIBuildStatus.PENDING == "pending"
    assert CIBuildStatus.RUNNING == "running"
    assert CIBuildStatus.SUCCESS == "success"
    assert CIBuildStatus.FAILURE == "failure"
    assert CIBuildStatus.CANCELLED == "cancelled"
    assert CIBuildStatus.UNKNOWN == "unknown"


def test_ci_build_defaults() -> None:
    build = CIBuild(
        build_id="123",
        provider=CIProvider.GITHUB_ACTIONS,
        status=CIBuildStatus.SUCCESS,
        repo_url="https://github.com/org/repo",
        branch="main",
        commit_sha="abc123",
    )
    assert build.pipeline_name == ""
    assert build.build_url == ""
    assert build.started_at is None
    assert build.finished_at is None
    assert build.metadata == {}


def test_ci_webhook_payload_defaults() -> None:
    payload = CIWebhookPayload(provider=CIProvider.CONCOURSE)
    assert payload.headers == {}
    assert payload.body == {}
