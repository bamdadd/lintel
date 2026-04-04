"""Tests for the onboarding wizard endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import os

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)


class TestOnboardingStatus:
    def test_initial_status_no_provider_no_repo(self, client: TestClient) -> None:
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_ai_provider"] is False
        assert data["has_repo"] is False
        assert data["is_complete"] is False
        assert data["has_chat"] is False
        assert data["current_step"] == "workspace"
        assert "steps" in data

    def test_status_after_adding_provider(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "Ollama",
                "api_base": "http://localhost:11434",
            },
        )
        assert resp.status_code == 201, resp.json()
        resp = client.get("/api/v1/onboarding/status")
        data = resp.json()
        assert data["has_ai_provider"] is True
        assert data["providers_count"] == 1
        assert data["is_complete"] is False  # still no repo

    def test_status_complete_with_provider_and_repo(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "Ollama",
                "api_base": "http://localhost:11434",
            },
        )
        client.post(
            "/api/v1/repositories",
            json={
                "name": "test-repo",
                "url": "https://github.com/org/repo",
            },
        )
        resp = client.get("/api/v1/onboarding/status")
        data = resp.json()
        assert data["has_ai_provider"] is True
        assert data["has_repo"] is True
        assert data["is_complete"] is True
        assert data["repos_count"] == 1


class TestOnboardingSteps:
    def test_complete_workspace_step(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "My Team"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["step"] == "workspace"
        assert data["status"] == "completed"
        assert data["current_step"] == "slack"

    def test_skip_optional_step(self, client: TestClient) -> None:
        client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "My Team"}},
        )
        resp = client.post(
            "/api/v1/onboarding/steps/slack",
            json={"action": "skip"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert data["current_step"] == "repo"

    def test_cannot_skip_required_step(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "skip"},
        )
        assert resp.status_code == 400
        assert "required" in resp.json()["detail"]

    def test_cannot_repeat_completed_step(self, client: TestClient) -> None:
        client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "Test"}},
        )
        resp = client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "Test Again"}},
        )
        assert resp.status_code == 409

    def test_unknown_step_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/onboarding/steps/foobar",
            json={"action": "complete"},
        )
        assert resp.status_code == 404

    def test_cannot_post_to_done(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/onboarding/steps/done",
            json={"action": "complete"},
        )
        assert resp.status_code == 400

    def test_workspace_requires_name(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {}},
        )
        assert resp.status_code == 422

    def test_full_wizard_flow(self, client: TestClient) -> None:
        """Walk through the entire onboarding wizard."""
        # 1. Workspace
        resp = client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "Acme Corp"}},
        )
        assert resp.json()["current_step"] == "slack"

        # 2. Skip slack
        resp = client.post(
            "/api/v1/onboarding/steps/slack",
            json={"action": "skip"},
        )
        assert resp.json()["current_step"] == "repo"

        # 3. Register a repo first, then complete step
        client.post(
            "/api/v1/repositories",
            json={"name": "my-repo", "url": "https://github.com/acme/app"},
        )
        resp = client.post(
            "/api/v1/onboarding/steps/repo",
            json={"action": "complete", "data": {}},
        )
        assert resp.json()["current_step"] == "project"

        # 4. Project
        resp = client.post(
            "/api/v1/onboarding/steps/project",
            json={"action": "complete", "data": {"name": "Main Project"}},
        )
        assert resp.json()["current_step"] == "team"

        # 5. Skip team
        resp = client.post(
            "/api/v1/onboarding/steps/team",
            json={"action": "skip"},
        )
        assert resp.json()["current_step"] == "ai_model"

        # 6. Register AI provider first, then complete
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "Ollama",
                "api_base": "http://localhost:11434",
            },
        )
        resp = client.post(
            "/api/v1/onboarding/steps/ai_model",
            json={"action": "complete", "data": {}},
        )
        assert resp.json()["current_step"] == "compliance"

        # 7. Skip compliance
        resp = client.post(
            "/api/v1/onboarding/steps/compliance",
            json={"action": "skip"},
        )
        assert resp.json()["current_step"] == "done"

        # Check final status
        status = client.get("/api/v1/onboarding/status").json()
        assert status["is_complete"] is True
        assert status["current_step"] == "done"

    def test_compliance_validates_level(self, client: TestClient) -> None:
        # Complete prerequisite steps first
        client.post(
            "/api/v1/onboarding/steps/workspace",
            json={"action": "complete", "data": {"workspace_name": "Test"}},
        )
        for step in ("slack", "team"):
            client.post(f"/api/v1/onboarding/steps/{step}", json={"action": "skip"})
        client.post(
            "/api/v1/repositories",
            json={"name": "r", "url": "https://github.com/o/r"},
        )
        client.post(
            "/api/v1/onboarding/steps/repo",
            json={"action": "complete", "data": {}},
        )
        client.post(
            "/api/v1/onboarding/steps/project",
            json={"action": "complete", "data": {"name": "P"}},
        )
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "p1",
                "provider_type": "ollama",
                "name": "O",
                "api_base": "http://localhost:11434",
            },
        )
        client.post(
            "/api/v1/onboarding/steps/ai_model",
            json={"action": "complete", "data": {}},
        )
        resp = client.post(
            "/api/v1/onboarding/steps/compliance",
            json={"action": "complete", "data": {"level": "invalid"}},
        )
        assert resp.status_code == 422
