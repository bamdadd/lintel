"""Tests for the onboarding status endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import os

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest


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
