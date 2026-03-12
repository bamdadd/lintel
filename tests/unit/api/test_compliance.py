"""Tests for compliance & governance API endpoints."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


# Helper to create a project first (most entities require project_id)
def _create_project(client: TestClient, project_id: str = "proj-1") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert resp.status_code == 201
    return resp.json()


# ======================== REGULATIONS ========================


class TestRegulationsAPI:
    def test_create_regulation(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/regulations",
            json={
                "regulation_id": "reg-1",
                "project_id": "proj-1",
                "name": "HIPAA",
                "authority": "HHS",
                "risk_level": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "HIPAA"
        assert data["authority"] == "HHS"
        assert data["risk_level"] == "high"

    def test_list_regulations_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/regulations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_regulations_filter_by_project(self, client: TestClient) -> None:
        _create_project(client, "proj-a")
        _create_project(client, "proj-b")
        client.post("/api/v1/regulations", json={"regulation_id": "reg-a", "project_id": "proj-a", "name": "GDPR"})
        client.post("/api/v1/regulations", json={"regulation_id": "reg-b", "project_id": "proj-b", "name": "HIPAA"})
        resp = client.get("/api/v1/regulations?project_id=proj-a")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "GDPR"

    def test_get_regulation(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "reg-2", "project_id": "proj-1", "name": "GDPR"})
        resp = client.get("/api/v1/regulations/reg-2")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GDPR"

    def test_get_regulation_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/regulations/nonexistent")
        assert resp.status_code == 404

    def test_update_regulation(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "reg-3", "project_id": "proj-1", "name": "IEC 62304"})
        resp = client.patch("/api/v1/regulations/reg-3", json={"name": "IEC 62304:2015", "risk_level": "critical"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "IEC 62304:2015"
        assert resp.json()["risk_level"] == "critical"

    def test_delete_regulation(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "reg-4", "project_id": "proj-1", "name": "To Delete"})
        resp = client.delete("/api/v1/regulations/reg-4")
        assert resp.status_code == 204
        assert client.get("/api/v1/regulations/reg-4").status_code == 404

    def test_create_duplicate_regulation_returns_409(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "reg-dup", "project_id": "proj-1", "name": "HIPAA"})
        resp = client.post("/api/v1/regulations", json={"regulation_id": "reg-dup", "project_id": "proj-1", "name": "HIPAA"})
        assert resp.status_code == 409


# ======================== COMPLIANCE POLICIES ========================


class TestCompliancePoliciesAPI:
    def test_create_compliance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "reg-1", "project_id": "proj-1", "name": "HIPAA"})
        resp = client.post(
            "/api/v1/compliance-policies",
            json={
                "policy_id": "cpol-1",
                "project_id": "proj-1",
                "name": "PHI Handling Policy",
                "regulation_ids": ["reg-1"],
                "risk_level": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "PHI Handling Policy"
        assert data["regulation_ids"] == ["reg-1"]

    def test_list_compliance_policies(self, client: TestClient) -> None:
        resp = client.get("/api/v1/compliance-policies")
        assert resp.status_code == 200

    def test_update_compliance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/compliance-policies", json={"policy_id": "cpol-2", "project_id": "proj-1", "name": "Policy A"})
        resp = client.patch("/api/v1/compliance-policies/cpol-2", json={"name": "Policy A v2", "status": "active"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Policy A v2"

    def test_delete_compliance_policy(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/compliance-policies", json={"policy_id": "cpol-3", "project_id": "proj-1", "name": "Delete Me"})
        resp = client.delete("/api/v1/compliance-policies/cpol-3")
        assert resp.status_code == 204


# ======================== PROCEDURES ========================


class TestProceduresAPI:
    def test_create_procedure(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/procedures",
            json={
                "procedure_id": "proc-1",
                "project_id": "proj-1",
                "name": "Code Review Procedure",
                "steps": ["Open PR", "Assign reviewer", "Review", "Merge"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Code Review Procedure"
        assert len(data["steps"]) == 4

    def test_list_procedures(self, client: TestClient) -> None:
        resp = client.get("/api/v1/procedures")
        assert resp.status_code == 200

    def test_update_procedure(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/procedures", json={"procedure_id": "proc-2", "project_id": "proj-1", "name": "Proc A"})
        resp = client.patch("/api/v1/procedures/proc-2", json={"workflow_definition_id": "wf-1"})
        assert resp.status_code == 200
        assert resp.json()["workflow_definition_id"] == "wf-1"

    def test_delete_procedure(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/procedures", json={"procedure_id": "proc-3", "project_id": "proj-1", "name": "Delete Me"})
        resp = client.delete("/api/v1/procedures/proc-3")
        assert resp.status_code == 204


# ======================== PRACTICES ========================


class TestPracticesAPI:
    def test_create_practice(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/practices",
            json={
                "practice_id": "prac-1",
                "project_id": "proj-1",
                "name": "Static Analysis",
                "automation_status": "fully_automated",
                "evidence_type": "test_results",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["automation_status"] == "fully_automated"

    def test_list_and_filter_practices(self, client: TestClient) -> None:
        _create_project(client, "proj-x")
        client.post("/api/v1/practices", json={"practice_id": "prac-a", "project_id": "proj-x", "name": "Prac A"})
        resp = client.get("/api/v1/practices?project_id=proj-x")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_practice(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/practices", json={"practice_id": "prac-d", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/practices/prac-d").status_code == 204


# ======================== STRATEGIES ========================


class TestStrategiesAPI:
    def test_create_strategy(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/strategies",
            json={
                "strategy_id": "strat-1",
                "project_id": "proj-1",
                "name": "Testing Strategy",
                "objectives": ["100% coverage", "Mutation testing"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Testing Strategy"
        assert len(data["objectives"]) == 2

    def test_update_strategy(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/strategies", json={"strategy_id": "strat-2", "project_id": "proj-1", "name": "Sec Strategy"})
        resp = client.patch("/api/v1/strategies/strat-2", json={"owner": "security-team"})
        assert resp.status_code == 200
        assert resp.json()["owner"] == "security-team"

    def test_delete_strategy(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/strategies", json={"strategy_id": "strat-3", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/strategies/strat-3").status_code == 204


# ======================== KPIs ========================


class TestKPIsAPI:
    def test_create_kpi(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/kpis",
            json={
                "kpi_id": "kpi-1",
                "project_id": "proj-1",
                "name": "Code Coverage",
                "target_value": "90",
                "current_value": "75",
                "unit": "%",
                "direction": "increase",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_value"] == "90"
        assert data["direction"] == "increase"

    def test_update_kpi_value(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/kpis", json={"kpi_id": "kpi-2", "project_id": "proj-1", "name": "MTTR", "current_value": "45"})
        resp = client.patch("/api/v1/kpis/kpi-2", json={"current_value": "30"})
        assert resp.status_code == 200
        assert resp.json()["current_value"] == "30"

    def test_delete_kpi(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/kpis", json={"kpi_id": "kpi-3", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/kpis/kpi-3").status_code == 204


# ======================== EXPERIMENTS ========================


class TestExperimentsAPI:
    def test_create_experiment(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/experiments",
            json={
                "experiment_id": "exp-1",
                "project_id": "proj-1",
                "name": "AI Code Review",
                "hypothesis": "AI review reduces bug rate by 30%",
                "status": "running",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["hypothesis"] == "AI review reduces bug rate by 30%"
        assert data["status"] == "running"

    def test_update_experiment_outcome(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/experiments", json={"experiment_id": "exp-2", "project_id": "proj-1", "name": "Exp 2"})
        resp = client.patch("/api/v1/experiments/exp-2", json={"status": "completed", "outcome": "Positive: 35% reduction"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_delete_experiment(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/experiments", json={"experiment_id": "exp-3", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/experiments/exp-3").status_code == 204


# ======================== COMPLIANCE METRICS ========================


class TestComplianceMetricsAPI:
    def test_create_compliance_metric(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/compliance-metrics",
            json={
                "metric_id": "met-1",
                "project_id": "proj-1",
                "name": "Vulnerability Count",
                "value": "3",
                "unit": "count",
                "source": "automated",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["source"] == "automated"

    def test_delete_compliance_metric(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/compliance-metrics", json={"metric_id": "met-2", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/compliance-metrics/met-2").status_code == 204


# ======================== KNOWLEDGE ENTRIES ========================


class TestKnowledgeEntriesAPI:
    def test_create_knowledge_entry(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/knowledge-entries",
            json={
                "entry_id": "ke-1",
                "project_id": "proj-1",
                "name": "User Auth Flow",
                "entry_type": "logic_flow",
                "source_file": "src/auth.py",
                "source_lines": "10-50",
                "code_snippet": "def authenticate(user):\n    ...",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entry_type"] == "logic_flow"
        assert data["source_file"] == "src/auth.py"

    def test_list_knowledge_entries(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge-entries")
        assert resp.status_code == 200

    def test_update_knowledge_entry(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/knowledge-entries", json={"entry_id": "ke-2", "project_id": "proj-1", "name": "API"})
        resp = client.patch("/api/v1/knowledge-entries/ke-2", json={"entry_type": "api_endpoint", "description": "REST API"})
        assert resp.status_code == 200
        assert resp.json()["entry_type"] == "api_endpoint"

    def test_delete_knowledge_entry(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/knowledge-entries", json={"entry_id": "ke-3", "project_id": "proj-1", "name": "Delete Me"})
        assert client.delete("/api/v1/knowledge-entries/ke-3").status_code == 204


# ======================== KNOWLEDGE EXTRACTIONS ========================


class TestKnowledgeExtractionsAPI:
    def test_start_extraction(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.post(
            "/api/v1/knowledge-extractions",
            json={"run_id": "ext-1", "project_id": "proj-1", "repo_id": "repo-1"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_list_extractions(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge-extractions")
        assert resp.status_code == 200

    def test_get_extraction(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/knowledge-extractions", json={"run_id": "ext-2", "project_id": "proj-1"})
        resp = client.get("/api/v1/knowledge-extractions/ext-2")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "ext-2"


# ======================== COMPLIANCE OVERVIEW ========================


class TestComplianceOverviewAPI:
    def test_overview_empty_project(self, client: TestClient) -> None:
        _create_project(client)
        resp = client.get("/api/v1/compliance/overview/proj-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-1"
        assert data["counts"]["regulations"] == 0
        assert data["counts"]["policies"] == 0

    def test_overview_with_data(self, client: TestClient) -> None:
        _create_project(client)
        client.post("/api/v1/regulations", json={"regulation_id": "r1", "project_id": "proj-1", "name": "HIPAA", "risk_level": "high"})
        client.post("/api/v1/regulations", json={"regulation_id": "r2", "project_id": "proj-1", "name": "GDPR", "risk_level": "medium"})
        client.post("/api/v1/compliance-policies", json={"policy_id": "p1", "project_id": "proj-1", "name": "Policy 1", "regulation_ids": ["r1"]})
        client.post("/api/v1/strategies", json={"strategy_id": "s1", "project_id": "proj-1", "name": "Testing Strategy"})
        client.post("/api/v1/kpis", json={"kpi_id": "k1", "project_id": "proj-1", "name": "Coverage"})

        resp = client.get("/api/v1/compliance/overview/proj-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["counts"]["regulations"] == 2
        assert data["counts"]["policies"] == 1
        assert data["counts"]["strategies"] == 1
        assert data["counts"]["kpis"] == 1
        assert "high" in data["risk_distribution"]
        assert len(data["cascade"]["regulations"]) == 2


# ======================== CASCADE RELATIONSHIP TESTS ========================


class TestComplianceCascade:
    """Test the full cascade: Regulation → Policy → Procedure → Practice."""

    def test_full_cascade(self, client: TestClient) -> None:
        _create_project(client)

        # Create regulation
        client.post("/api/v1/regulations", json={
            "regulation_id": "reg-cascade",
            "project_id": "proj-1",
            "name": "IEC 62304",
            "authority": "IEC",
            "risk_level": "critical",
        })

        # Create policy linked to regulation
        client.post("/api/v1/compliance-policies", json={
            "policy_id": "pol-cascade",
            "project_id": "proj-1",
            "name": "Software Lifecycle Policy",
            "regulation_ids": ["reg-cascade"],
            "risk_level": "high",
        })

        # Create procedure linked to policy
        client.post("/api/v1/procedures", json={
            "procedure_id": "proc-cascade",
            "project_id": "proj-1",
            "name": "Design Review Procedure",
            "policy_ids": ["pol-cascade"],
            "steps": ["Prepare", "Review", "Document", "Approve"],
        })

        # Create strategy
        client.post("/api/v1/strategies", json={
            "strategy_id": "strat-cascade",
            "project_id": "proj-1",
            "name": "Quality Strategy",
        })

        # Create practice linked to both procedure and strategy
        client.post("/api/v1/practices", json={
            "practice_id": "prac-cascade",
            "project_id": "proj-1",
            "name": "Peer Code Review",
            "procedure_ids": ["proc-cascade"],
            "strategy_ids": ["strat-cascade"],
            "automation_status": "semi_automated",
        })

        # Verify the overview captures the full cascade
        resp = client.get("/api/v1/compliance/overview/proj-1")
        data = resp.json()
        assert data["counts"]["regulations"] == 1
        assert data["counts"]["policies"] == 1
        assert data["counts"]["procedures"] == 1
        assert data["counts"]["practices"] == 1
        assert data["counts"]["strategies"] == 1

        # Verify practice has both links
        prac = client.get("/api/v1/practices/prac-cascade").json()
        assert "proc-cascade" in prac["procedure_ids"]
        assert "strat-cascade" in prac["strategy_ids"]
