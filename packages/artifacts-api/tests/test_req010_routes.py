"""API-level and integration tests for REQ-010 artifact endpoints."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    import httpx

from lintel.artifacts_api.routes import (
    artifact_content_store_provider,
    code_artifact_store_provider,
    coverage_metric_store_provider,
    parsed_result_store_provider,
    pipeline_store_provider,
    quality_gate_rule_store_provider,
    router,
    test_result_store_provider,
)
from lintel.artifacts_api.store import (
    CodeArtifactStore,
    CoverageMetricStore,
    ParsedTestResultStore,
    QualityGateRuleStore,
    TestResultStore,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_JUNIT = b"""<?xml version="1.0"?>
<testsuite name="test" tests="2" failures="1">
  <testcase name="test_pass" classname="suite" time="0.1"/>
  <testcase name="test_fail" classname="suite" time="0.2">
    <failure message="oops">details</failure>
  </testcase>
</testsuite>"""

SAMPLE_LCOV = b"""SF:src/main.py
DA:1,1
DA:2,0
LH:1
LF:2
end_of_record"""

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class MockArtifactStore:
    """Minimal ArtifactStore stub for tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def store(
        self,
        artifact_id: str,
        content: bytes,
        metadata: dict[str, object],
    ) -> str:
        self._data[artifact_id] = content
        return f"mock://{artifact_id}"

    async def retrieve(self, artifact_id: str) -> bytes:
        if artifact_id not in self._data:
            raise KeyError(artifact_id)
        return self._data[artifact_id]

    async def list_refs(self, run_id: str) -> list[object]:
        return []


class _FakePipelineStore:
    async def get(self, run_id: str) -> object | None:
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> Generator[TestClient]:
    code_artifact_store_provider.override(CodeArtifactStore())
    test_result_store_provider.override(TestResultStore())
    pipeline_store_provider.override(_FakePipelineStore())
    artifact_content_store_provider.override(MockArtifactStore())
    parsed_result_store_provider.override(ParsedTestResultStore())
    coverage_metric_store_provider.override(CoverageMetricStore())
    quality_gate_rule_store_provider.override(QualityGateRuleStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    code_artifact_store_provider.override(None)
    test_result_store_provider.override(None)
    pipeline_store_provider.override(None)
    artifact_content_store_provider.override(None)
    parsed_result_store_provider.override(None)
    coverage_metric_store_provider.override(None)
    quality_gate_rule_store_provider.override(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _upload_junit(
    client: TestClient, run_id: str = "run-1", project_id: str = "proj-1"
) -> httpx.Response:
    return client.post(
        "/api/v1/artifacts/upload",
        json={
            "run_id": run_id,
            "project_id": project_id,
            "artifact_type": "test_result",
            "extension": ".xml",
            "content_base64": _b64(SAMPLE_JUNIT),
        },
    )


def _upload_lcov(
    client: TestClient, run_id: str = "run-1", project_id: str = "proj-1"
) -> httpx.Response:
    return client.post(
        "/api/v1/artifacts/upload",
        json={
            "run_id": run_id,
            "project_id": project_id,
            "artifact_type": "coverage",
            "extension": ".info",
            "content_base64": _b64(SAMPLE_LCOV),
        },
    )


# ===================================================================
# Upload endpoint tests
# ===================================================================


class TestUploadArtifact:
    """Tests for POST /artifacts/upload."""

    def test_upload_junit_xml(self, client: TestClient) -> None:
        resp = _upload_junit(client)
        assert resp.status_code == 201
        data = resp.json()
        assert "artifact_id" in data
        assert "parsed" in data
        parsed = data["parsed"]
        assert parsed["total"] == 2
        assert parsed["passed"] == 1
        assert parsed["failed"] == 1

    def test_upload_lcov_coverage(self, client: TestClient) -> None:
        resp = _upload_lcov(client)
        assert resp.status_code == 201
        data = resp.json()
        assert "artifact_id" in data
        assert "coverage" in data
        coverage = data["coverage"]
        assert coverage["lines_covered"] == 1
        assert coverage["lines_total"] == 2

    def test_upload_unknown_type_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "unknown",
                "content_base64": _b64(b"data"),
            },
        )
        assert resp.status_code == 400
        assert "unknown" in resp.json()["detail"].lower()

    def test_upload_invalid_extension_returns_error(self, client: TestClient) -> None:
        """POST with artifact_type='test_result' and unsupported extension '.xyz'
        triggers a ValueError from the parser registry."""
        with pytest.raises(ValueError, match="No artifact parser"):
            client.post(
                "/api/v1/artifacts/upload",
                json={
                    "run_id": "run-1",
                    "project_id": "proj-1",
                    "artifact_type": "test_result",
                    "extension": ".xyz",
                    "content_base64": _b64(b"data"),
                },
            )


# ===================================================================
# Test results endpoint tests
# ===================================================================


class TestGetTestResults:
    """Tests for GET /artifacts/test-results/{run_id}."""

    def test_get_test_results_by_run(self, client: TestClient) -> None:
        upload_resp = _upload_junit(client, run_id="run-tr")
        assert upload_resp.status_code == 201

        resp = client.get("/api/v1/artifacts/test-results/run-tr")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["total"] == 2
        assert data[0]["run_id"] == "run-tr"

    def test_get_test_results_empty_run(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts/test-results/nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []


# ===================================================================
# Coverage endpoint tests
# ===================================================================


class TestGetCoverage:
    """Tests for GET /artifacts/coverage/{run_id}."""

    def test_get_coverage_by_run(self, client: TestClient) -> None:
        upload_resp = _upload_lcov(client, run_id="run-cov")
        assert upload_resp.status_code == 201

        resp = client.get("/api/v1/artifacts/coverage/run-cov")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lines_covered"] == 1
        assert data["lines_total"] == 2
        assert data["run_id"] == "run-cov"

    def test_get_coverage_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/artifacts/coverage/nonexistent")
        assert resp.status_code == 404


# ===================================================================
# Quality gate rule endpoint tests
# ===================================================================


class TestQualityGateRules:
    """Tests for /projects/{project_id}/quality-gate-rules endpoints."""

    def test_create_quality_gate_rule(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj1/quality-gate-rules",
            json={
                "rule_type": "min_pass_rate",
                "threshold": 80.0,
                "severity": "error",
                "enabled": True,
            },
        )
        assert resp.status_code == 201
        rule = resp.json()
        assert rule["rule_type"] == "min_pass_rate"
        assert rule["threshold"] == 80.0
        assert rule["project_id"] == "proj1"
        assert rule["severity"] == "error"
        assert rule["enabled"] is True
        assert "rule_id" in rule

    def test_list_quality_gate_rules(self, client: TestClient) -> None:
        # Create two rules for proj1
        client.post(
            "/api/v1/projects/proj1/quality-gate-rules",
            json={
                "rule_id": "qr-1",
                "rule_type": "min_pass_rate",
                "threshold": 80.0,
            },
        )
        client.post(
            "/api/v1/projects/proj1/quality-gate-rules",
            json={
                "rule_id": "qr-2",
                "rule_type": "min_coverage",
                "threshold": 70.0,
            },
        )

        resp = client.get("/api/v1/projects/proj1/quality-gate-rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) == 2
        rule_ids = {r["rule_id"] for r in rules}
        assert rule_ids == {"qr-1", "qr-2"}

    def test_list_rules_different_project(self, client: TestClient) -> None:
        # Create a rule for proj1
        client.post(
            "/api/v1/projects/proj1/quality-gate-rules",
            json={
                "rule_type": "min_pass_rate",
                "threshold": 80.0,
            },
        )

        # List rules for proj2 - should be empty
        resp = client.get("/api/v1/projects/proj2/quality-gate-rules")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_quality_gate_rule(self, client: TestClient) -> None:
        # Create a rule
        client.post(
            "/api/v1/projects/proj1/quality-gate-rules",
            json={
                "rule_id": "qr-del",
                "rule_type": "min_pass_rate",
                "threshold": 90.0,
            },
        )

        # Delete it
        resp = client.delete("/api/v1/projects/proj1/quality-gate-rules/qr-del")
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get("/api/v1/projects/proj1/quality-gate-rules")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_nonexistent_rule(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/projects/proj1/quality-gate-rules/nonexistent")
        assert resp.status_code == 404


# ===================================================================
# Integration / end-to-end tests
# ===================================================================


class TestEndToEndArtifactFlow:
    """End-to-end: upload artifact -> retrieve parsed results -> set quality gate rules."""

    def test_full_flow(self, client: TestClient) -> None:
        # 1. Create quality gate rules
        client.post(
            "/api/v1/projects/proj-1/quality-gate-rules",
            json={"rule_type": "min_pass_rate", "threshold": 90.0},
        )
        client.post(
            "/api/v1/projects/proj-1/quality-gate-rules",
            json={"rule_type": "min_coverage", "threshold": 60.0},
        )

        # 2. Upload test result
        upload_resp = _upload_junit(client, run_id="run-e2e", project_id="proj-1")
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert upload_data["parsed"]["total"] == 2

        # 3. Upload coverage
        cov_resp = _upload_lcov(client, run_id="run-e2e", project_id="proj-1")
        assert cov_resp.status_code == 201

        # 4. Retrieve test results
        tr_resp = client.get("/api/v1/artifacts/test-results/run-e2e")
        assert tr_resp.status_code == 200
        assert len(tr_resp.json()) == 1

        # 5. Retrieve coverage
        cov_get_resp = client.get("/api/v1/artifacts/coverage/run-e2e")
        assert cov_get_resp.status_code == 200
        assert cov_get_resp.json()["lines_covered"] == 1

        # 6. Verify rules are still there
        rules_resp = client.get("/api/v1/projects/proj-1/quality-gate-rules")
        assert rules_resp.status_code == 200
        assert len(rules_resp.json()) == 2

    def test_multiple_uploads_same_run(self, client: TestClient) -> None:
        """Multiple test result uploads for the same run accumulate in the store."""
        _upload_junit(client, run_id="run-multi")
        _upload_junit(client, run_id="run-multi")

        resp = client.get("/api/v1/artifacts/test-results/run-multi")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_uploads_isolated_by_run(self, client: TestClient) -> None:
        """Uploads for different runs are isolated when queried."""
        _upload_junit(client, run_id="run-a")
        _upload_junit(client, run_id="run-b")

        resp_a = client.get("/api/v1/artifacts/test-results/run-a")
        resp_b = client.get("/api/v1/artifacts/test-results/run-b")
        assert len(resp_a.json()) == 1
        assert len(resp_b.json()) == 1
        assert resp_a.json()[0]["run_id"] == "run-a"
        assert resp_b.json()[0]["run_id"] == "run-b"
