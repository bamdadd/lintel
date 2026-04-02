"""Integration tests for REQ-010 artifact upload and quality gate endpoints."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.artifacts_api.routes import (
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


class _FakePipelineStore:
    async def get(self, run_id: str) -> object | None:
        return None


@pytest.fixture()
def client() -> Generator[TestClient]:
    code_artifact_store_provider.override(CodeArtifactStore())
    test_result_store_provider.override(TestResultStore())
    pipeline_store_provider.override(_FakePipelineStore())
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
    parsed_result_store_provider.override(None)
    coverage_metric_store_provider.override(None)
    quality_gate_rule_store_provider.override(None)


SAMPLE_JUNIT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="suite1" tests="3" failures="1" errors="0">
    <testcase classname="mod.Test" name="test_pass" time="0.01"/>
    <testcase classname="mod.Test" name="test_also_pass" time="0.02"/>
    <testcase classname="mod.Test" name="test_fail" time="0.03">
      <failure message="assertion error">Expected 1 got 2</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

SAMPLE_LCOV = """\
SF:src/app.py
DA:1,1
DA:2,1
DA:3,0
LH:2
LF:3
end_of_record
"""


class TestUploadArtifact:
    def test_upload_test_result(self, client: TestClient) -> None:
        content_b64 = base64.b64encode(SAMPLE_JUNIT_XML.encode()).decode()
        resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "test_result",
                "extension": ".xml",
                "content_base64": content_b64,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "artifact_id" in data
        assert "parsed" in data
        assert data["parsed"]["total"] == 3
        assert data["parsed"]["passed"] == 2
        assert data["parsed"]["failed"] == 1

    def test_upload_coverage(self, client: TestClient) -> None:
        content_b64 = base64.b64encode(SAMPLE_LCOV.encode()).decode()
        resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "coverage",
                "extension": ".info",
                "content_base64": content_b64,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "artifact_id" in data
        assert "coverage" in data
        assert data["coverage"]["lines_covered"] == 2
        assert data["coverage"]["lines_total"] == 3

    def test_upload_bad_artifact_type(self, client: TestClient) -> None:
        content_b64 = base64.b64encode(b"data").decode()
        resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "unknown",
                "content_base64": content_b64,
            },
        )
        assert resp.status_code == 400

    def test_get_test_results_by_run(self, client: TestClient) -> None:
        # Upload first
        content_b64 = base64.b64encode(SAMPLE_JUNIT_XML.encode()).decode()
        client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "test_result",
                "extension": ".xml",
                "content_base64": content_b64,
            },
        )
        resp = client.get("/api/v1/artifacts/test-results/run-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["total"] == 3

    def test_get_coverage_by_run(self, client: TestClient) -> None:
        content_b64 = base64.b64encode(SAMPLE_LCOV.encode()).decode()
        client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-1",
                "project_id": "proj-1",
                "artifact_type": "coverage",
                "extension": ".info",
                "content_base64": content_b64,
            },
        )
        resp = client.get("/api/v1/artifacts/coverage/run-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert data["lines_covered"] == 2


class TestQualityGateRulesAPI:
    def test_create_and_list_rules(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj-1/quality-gate-rules",
            json={
                "rule_type": "min_coverage",
                "threshold": 80.0,
                "severity": "error",
            },
        )
        assert resp.status_code == 201
        rule = resp.json()
        assert rule["rule_type"] == "min_coverage"
        assert rule["threshold"] == 80.0

        # List rules
        resp = client.get("/api/v1/projects/proj-1/quality-gate-rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) == 1

    def test_delete_rule(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/proj-1/quality-gate-rules",
            json={
                "rule_id": "qr-del",
                "rule_type": "min_pass_rate",
                "threshold": 90.0,
            },
        )
        assert resp.status_code == 201

        resp = client.delete("/api/v1/projects/proj-1/quality-gate-rules/qr-del")
        assert resp.status_code == 204

        resp = client.get("/api/v1/projects/proj-1/quality-gate-rules")
        assert len(resp.json()) == 0

    def test_delete_missing_rule(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/projects/proj-1/quality-gate-rules/missing")
        assert resp.status_code == 404


class TestEndToEndArtifactFlow:
    """End-to-end: upload artifact → retrieve parsed results → set quality gate rules."""

    def test_full_flow(self, client: TestClient) -> None:
        # 1. Create quality gate rule
        client.post(
            "/api/v1/projects/proj-1/quality-gate-rules",
            json={
                "rule_type": "min_pass_rate",
                "threshold": 90.0,
            },
        )

        # 2. Upload test result
        content_b64 = base64.b64encode(SAMPLE_JUNIT_XML.encode()).decode()
        upload_resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-e2e",
                "project_id": "proj-1",
                "artifact_type": "test_result",
                "extension": ".xml",
                "content_base64": content_b64,
            },
        )
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert upload_data["parsed"]["total"] == 3

        # 3. Upload coverage
        cov_b64 = base64.b64encode(SAMPLE_LCOV.encode()).decode()
        cov_resp = client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-e2e",
                "project_id": "proj-1",
                "artifact_type": "coverage",
                "extension": ".info",
                "content_base64": cov_b64,
            },
        )
        assert cov_resp.status_code == 201

        # 4. Retrieve results
        tr_resp = client.get("/api/v1/artifacts/test-results/run-e2e")
        assert tr_resp.status_code == 200
        assert len(tr_resp.json()) == 1

        cov_get_resp = client.get("/api/v1/artifacts/coverage/run-e2e")
        assert cov_get_resp.status_code == 200
        assert cov_get_resp.json()["lines_covered"] == 2

        # 5. Verify rules are still there
        rules_resp = client.get("/api/v1/projects/proj-1/quality-gate-rules")
        assert rules_resp.status_code == 200
        assert len(rules_resp.json()) == 1

        # 6. Evaluate quality gates
        eval_resp = client.post(
            "/api/v1/projects/proj-1/quality-gates/evaluate?run_id=run-e2e",
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["overall"] == "fail"  # pass rate 66.7% < 90%
        assert eval_data["project_id"] == "proj-1"
        assert eval_data["run_id"] == "run-e2e"
        assert len(eval_data["results"]) == 1
        assert eval_data["results"][0]["passed"] is False
        assert eval_data["results"][0]["rule_type"] == "min_pass_rate"


class TestQualityGateEvaluation:
    """Tests for the quality gate evaluation endpoint."""

    def test_evaluate_no_rules(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/projects/no-rules/quality-gates/evaluate?run_id=run-1",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "pass"
        assert data["results"] == []

    def test_evaluate_pass_rate_passes(self, client: TestClient) -> None:
        # Create a lenient rule (50% pass rate)
        client.post(
            "/api/v1/projects/proj-eval/quality-gate-rules",
            json={"rule_type": "min_pass_rate", "threshold": 50.0},
        )
        # Upload test result (66.7% pass rate)
        content_b64 = base64.b64encode(SAMPLE_JUNIT_XML.encode()).decode()
        client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-pass",
                "project_id": "proj-eval",
                "artifact_type": "test_result",
                "extension": ".xml",
                "content_base64": content_b64,
            },
        )
        resp = client.post(
            "/api/v1/projects/proj-eval/quality-gates/evaluate?run_id=run-pass",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "pass"
        assert data["results"][0]["passed"] is True

    def test_evaluate_min_coverage_fails(self, client: TestClient) -> None:
        # Create strict coverage rule (80%)
        client.post(
            "/api/v1/projects/proj-cov/quality-gate-rules",
            json={"rule_type": "min_coverage", "threshold": 80.0},
        )
        # Upload coverage (66.7% coverage)
        cov_b64 = base64.b64encode(SAMPLE_LCOV.encode()).decode()
        client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-cov",
                "project_id": "proj-cov",
                "artifact_type": "coverage",
                "extension": ".info",
                "content_base64": cov_b64,
            },
        )
        resp = client.post(
            "/api/v1/projects/proj-cov/quality-gates/evaluate?run_id=run-cov",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "fail"
        assert data["results"][0]["passed"] is False
        assert "below threshold" in data["results"][0]["message"]

    def test_evaluate_warn_severity(self, client: TestClient) -> None:
        # Create warning-level rule
        client.post(
            "/api/v1/projects/proj-warn/quality-gate-rules",
            json={
                "rule_type": "min_pass_rate",
                "threshold": 99.0,
                "severity": "warn",
            },
        )
        # Upload test result (66.7% pass rate)
        content_b64 = base64.b64encode(SAMPLE_JUNIT_XML.encode()).decode()
        client.post(
            "/api/v1/artifacts/upload",
            json={
                "run_id": "run-warn",
                "project_id": "proj-warn",
                "artifact_type": "test_result",
                "extension": ".xml",
                "content_base64": content_b64,
            },
        )
        resp = client.post(
            "/api/v1/projects/proj-warn/quality-gates/evaluate?run_id=run-warn",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "warn"  # warning, not fail

    def test_evaluate_no_artifacts(self, client: TestClient) -> None:
        # Rule exists but no test results uploaded
        client.post(
            "/api/v1/projects/proj-empty/quality-gate-rules",
            json={"rule_type": "min_pass_rate", "threshold": 80.0},
        )
        resp = client.post(
            "/api/v1/projects/proj-empty/quality-gates/evaluate?run_id=no-run",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "fail"
        assert data["results"][0]["passed"] is False
        assert "No test results" in data["results"][0]["message"]
