"""Tests for CI/CD webhook endpoints (GitHub Actions, GitLab CI, generic)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.api.routes.webhooks import (
    _WEBHOOK_SECRET,
    _deployment_store_provider,
    router,
)


def _make_client() -> TestClient:
    from lintel.api.routes.webhooks import DeploymentStore

    store = DeploymentStore()
    _deployment_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _github_signature(payload: bytes) -> str:
    sig = hmac.new(_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestGitHubActionsWebhook:
    def test_workflow_run_completed_success(self) -> None:
        client = _make_client()
        body: dict[str, Any] = {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "name": "CI",
                "head_branch": "main",
                "head_sha": "abc123",
                "conclusion": "success",
                "html_url": "https://github.com/org/repo/actions/runs/12345",
                "run_started_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:05:00Z",
            },
            "repository": {
                "full_name": "org/repo",
                "html_url": "https://github.com/org/repo",
            },
            "sender": {"login": "alice"},
        }
        payload = json.dumps(body).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_type"] == "workflow_run"
        assert data["deployment"]["status"] == "succeeded"
        assert data["deployment"]["provider"] == "github"

    def test_workflow_run_completed_failure(self) -> None:
        client = _make_client()
        body: dict[str, Any] = {
            "action": "completed",
            "workflow_run": {
                "id": 99999,
                "name": "Deploy",
                "head_branch": "main",
                "head_sha": "def456",
                "conclusion": "failure",
                "html_url": "https://github.com/org/repo/actions/runs/99999",
                "run_started_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:10:00Z",
            },
            "repository": {
                "full_name": "org/repo",
                "html_url": "https://github.com/org/repo",
            },
            "sender": {"login": "bob"},
        }
        payload = json.dumps(body).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["deployment"]["status"] == "failed"

    def test_workflow_run_in_progress(self) -> None:
        client = _make_client()
        body: dict[str, Any] = {
            "action": "in_progress",
            "workflow_run": {
                "id": 55555,
                "name": "Build",
                "head_branch": "feat/x",
                "head_sha": "ghi789",
                "conclusion": None,
                "html_url": "https://github.com/org/repo/actions/runs/55555",
                "run_started_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
            "repository": {
                "full_name": "org/repo",
                "html_url": "https://github.com/org/repo",
            },
            "sender": {"login": "carol"},
        }
        payload = json.dumps(body).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["deployment"]["status"] == "started"


class TestGitLabPipelineWebhook:
    def test_pipeline_success(self) -> None:
        client = _make_client()
        body: dict[str, Any] = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 42,
                "ref": "main",
                "sha": "abc123",
                "status": "success",
                "created_at": "2025-01-01 00:00:00 UTC",
                "finished_at": "2025-01-01 00:05:00 UTC",
            },
            "project": {
                "path_with_namespace": "org/repo",
                "web_url": "https://gitlab.com/org/repo",
            },
            "user": {"username": "alice"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json=body,
            headers={"X-Gitlab-Token": _WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_type"] == "pipeline"
        assert data["deployment"]["status"] == "succeeded"
        assert data["deployment"]["provider"] == "gitlab"

    def test_pipeline_failed(self) -> None:
        client = _make_client()
        body: dict[str, Any] = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 43,
                "ref": "main",
                "sha": "def456",
                "status": "failed",
                "created_at": "2025-01-01T00:00:00Z",
                "finished_at": "2025-01-01T00:10:00Z",
            },
            "project": {
                "path_with_namespace": "org/repo",
                "web_url": "https://gitlab.com/org/repo",
            },
            "user": {"username": "bob"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json=body,
            headers={"X-Gitlab-Token": _WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        assert resp.json()["deployment"]["status"] == "failed"


class TestGenericCICDWebhook:
    def test_generic_success(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/v1/webhooks/ci-cd",
            json={
                "deployment_id": "deploy-1",
                "repo_name": "org/repo",
                "status": "succeeded",
                "workflow_name": "production-deploy",
                "branch": "main",
                "commit_sha": "abc123",
                "provider": "jenkins",
            },
            headers={"X-Webhook-Secret": _WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment"]["status"] == "succeeded"
        assert data["deployment"]["provider"] == "jenkins"

    def test_generic_missing_secret_returns_403(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/v1/webhooks/ci-cd",
            json={
                "deployment_id": "deploy-1",
                "repo_name": "org/repo",
                "status": "succeeded",
            },
        )
        assert resp.status_code == 403

    def test_generic_invalid_secret_returns_403(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/v1/webhooks/ci-cd",
            json={
                "deployment_id": "deploy-1",
                "repo_name": "org/repo",
                "status": "succeeded",
            },
            headers={"X-Webhook-Secret": "wrong-token"},
        )
        assert resp.status_code == 403


class TestDeploymentStore:
    def test_list_deployments(self) -> None:
        client = _make_client()
        resp = client.get("/api/v1/deployments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_deployments_populated_after_webhook(self) -> None:
        client = _make_client()
        client.post(
            "/api/v1/webhooks/ci-cd",
            json={
                "deployment_id": "d-1",
                "repo_name": "org/repo",
                "status": "succeeded",
                "provider": "jenkins",
            },
            headers={"X-Webhook-Secret": _WEBHOOK_SECRET},
        )
        resp = client.get("/api/v1/deployments")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["deployment_id"] == "d-1"
