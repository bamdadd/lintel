"""Tests for git webhook endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.api.routes.webhooks import (
    _git_event_listener_provider,
    router,
)
from lintel.domain.git_events import GitEventListener


def _make_client(listener: GitEventListener | None = None) -> TestClient:
    if listener is None:
        dispatcher = AsyncMock()
        dispatcher.dispatch = AsyncMock(return_value="run-123")
        listener = GitEventListener(dispatcher)
    _git_event_listener_provider.override(listener)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _github_signature(payload: bytes, secret: str = "test-secret") -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _github_push_payload() -> dict[str, Any]:
    return {
        "ref": "refs/heads/main",
        "before": "abc000",
        "after": "def111",
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
        },
        "sender": {"login": "alice"},
        "commits": [
            {
                "id": "def111",
                "message": "fix: something",
                "author": {"username": "alice"},
                "added": ["new.py"],
                "modified": ["old.py"],
                "removed": [],
            }
        ],
    }


def _github_pr_payload(action: str = "opened") -> dict[str, Any]:
    return {
        "action": action,
        "number": 42,
        "pull_request": {
            "title": "feat: add stuff",
            "body": "Description here",
            "head": {"ref": "feat/stuff"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/org/repo/pull/42",
        },
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
        },
        "sender": {"login": "bob"},
    }


def _github_review_payload() -> dict[str, Any]:
    return {
        "action": "submitted",
        "review": {
            "state": "approved",
            "body": "LGTM",
            "user": {"login": "carol"},
        },
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/org/repo/pull/42",
        },
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
        },
        "sender": {"login": "carol"},
    }


class TestGitHubWebhook:
    def test_push_event_returns_200(self) -> None:
        client = _make_client()
        payload = json.dumps(_github_push_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "push"

    def test_pr_event_returns_200(self) -> None:
        client = _make_client()
        payload = json.dumps(_github_pr_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "pull_request"

    def test_review_event_returns_200(self) -> None:
        client = _make_client()
        payload = json.dumps(_github_review_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request_review",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "pull_request_review"

    def test_invalid_signature_returns_403(self) -> None:
        client = _make_client()
        payload = json.dumps(_github_push_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=bad",
            },
        )
        assert resp.status_code == 403

    def test_missing_signature_returns_403(self) -> None:
        client = _make_client()
        payload = json.dumps(_github_push_payload()).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
            },
        )
        assert resp.status_code == 403

    def test_unknown_event_returns_200_ignored(self) -> None:
        client = _make_client()
        payload = json.dumps({"action": "created"}).encode()
        resp = client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "star",
                "X-Hub-Signature-256": _github_signature(payload),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "ignored"


class TestGitLabWebhook:
    def test_push_event_returns_200(self) -> None:
        client = _make_client()
        payload = {
            "object_kind": "push",
            "ref": "refs/heads/main",
            "before": "abc000",
            "after": "def111",
            "project": {
                "path_with_namespace": "org/repo",
                "web_url": "https://gitlab.com/org/repo",
            },
            "user_username": "alice",
            "commits": [
                {
                    "id": "def111",
                    "message": "fix: something",
                    "author": {"username": "alice"},
                    "added": ["new.py"],
                    "modified": ["old.py"],
                    "removed": [],
                }
            ],
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json=payload,
            headers={"X-Gitlab-Token": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "push"

    def test_mr_event_returns_200(self) -> None:
        client = _make_client()
        payload = {
            "object_kind": "merge_request",
            "object_attributes": {
                "action": "open",
                "iid": 99,
                "title": "feat: thing",
                "description": "desc",
                "source_branch": "feat/thing",
                "target_branch": "main",
                "url": "https://gitlab.com/org/repo/-/merge_requests/99",
            },
            "project": {
                "path_with_namespace": "org/repo",
                "web_url": "https://gitlab.com/org/repo",
            },
            "user": {"username": "bob"},
        }
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json=payload,
            headers={"X-Gitlab-Token": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "merge_request"

    def test_invalid_token_returns_403(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json={"object_kind": "push"},
            headers={"X-Gitlab-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_missing_token_returns_403(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/v1/webhooks/gitlab",
            json={"object_kind": "push"},
        )
        assert resp.status_code == 403
