"""Tests for AI firewall API endpoints (REQ-025)."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _create_rule(
    client: TestClient,
    name: str = "block-evil",
    pattern: str = "https://evil.example.com/*",
    action: str = "deny",
    priority: int = 10,
    agent_roles: list[str] | None = None,
    active: bool = True,
) -> dict:
    resp = client.post(
        "/api/v1/firewall/rules",
        json={
            "name": name,
            "pattern": pattern,
            "action": action,
            "priority": priority,
            "agent_roles": agent_roles or [],
            "active": active,
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestFirewallRuleCRUD:
    def test_create_rule(self, client: TestClient) -> None:
        data = _create_rule(client)
        assert data["name"] == "block-evil"
        assert data["pattern"] == "https://evil.example.com/*"
        assert data["action"] == "deny"
        assert data["priority"] == 10
        assert data["active"] is True

    def test_list_rules(self, client: TestClient) -> None:
        _create_rule(client, name="rule-a")
        _create_rule(client, name="rule-b", pattern="https://other.com/*")
        resp = client.get("/api/v1/firewall/rules")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        resp = client.get(f"/api/v1/firewall/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["rule_id"] == rule_id

    def test_get_rule_not_found(self, client: TestClient) -> None:
        assert client.get("/api/v1/firewall/rules/missing").status_code == 404

    def test_update_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        resp = client.patch(
            f"/api/v1/firewall/rules/{rule_id}",
            json={"name": "updated-name", "priority": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated-name"
        assert resp.json()["priority"] == 5

    def test_update_rule_not_found(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/firewall/rules/missing", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_rule(self, client: TestClient) -> None:
        created = _create_rule(client)
        rule_id = created["rule_id"]
        assert client.delete(f"/api/v1/firewall/rules/{rule_id}").status_code == 204
        assert client.get(f"/api/v1/firewall/rules/{rule_id}").status_code == 404

    def test_delete_rule_not_found(self, client: TestClient) -> None:
        assert client.delete("/api/v1/firewall/rules/missing").status_code == 404


class TestFirewallCheck:
    def test_check_allowed_no_rules(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/firewall/check",
            json={"url": "https://safe.example.com/api", "agent_id": "agent-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "allow"
        assert data["blocked"] is False
        assert data["matching_rule_id"] is None

    def test_check_blocked_by_rule(self, client: TestClient) -> None:
        _create_rule(client, pattern="https://evil.example.com/*", action="deny")
        resp = client.post(
            "/api/v1/firewall/check",
            json={"url": "https://evil.example.com/data", "agent_id": "agent-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "deny"
        assert data["blocked"] is True
        assert data["matching_rule_id"] is not None

    def test_check_log_only(self, client: TestClient) -> None:
        _create_rule(client, name="log-rule", pattern="https://monitored.com/*", action="log_only")
        resp = client.post(
            "/api/v1/firewall/check",
            json={"url": "https://monitored.com/api", "agent_id": "agent-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "log_only"
        assert data["blocked"] is False

    def test_check_priority_ordering(self, client: TestClient) -> None:
        _create_rule(
            client,
            name="broad-deny",
            pattern="https://*.example.com/*",
            action="deny",
            priority=100,
        )
        _create_rule(
            client,
            name="specific-allow",
            pattern="https://safe.example.com/*",
            action="allow",
            priority=10,
        )
        resp = client.post(
            "/api/v1/firewall/check",
            json={"url": "https://safe.example.com/api", "agent_id": "agent-1"},
        )
        data = resp.json()
        assert data["action"] == "allow"
        assert data["blocked"] is False

    def test_check_agent_role_filter(self, client: TestClient) -> None:
        _create_rule(
            client,
            name="coder-only",
            pattern="https://restricted.com/*",
            action="deny",
            agent_roles=["coder"],
        )
        # coder should be blocked
        resp = client.post(
            "/api/v1/firewall/check",
            json={
                "url": "https://restricted.com/api",
                "agent_id": "agent-1",
                "agent_role": "coder",
            },
        )
        assert resp.json()["blocked"] is True

        # reviewer should be allowed (rule doesn't apply)
        resp = client.post(
            "/api/v1/firewall/check",
            json={
                "url": "https://restricted.com/api",
                "agent_id": "agent-2",
                "agent_role": "reviewer",
            },
        )
        assert resp.json()["blocked"] is False

    def test_inactive_rule_ignored(self, client: TestClient) -> None:
        _create_rule(
            client, name="inactive", pattern="https://blocked.com/*", action="deny", active=False
        )
        resp = client.post(
            "/api/v1/firewall/check",
            json={"url": "https://blocked.com/api", "agent_id": "agent-1"},
        )
        assert resp.json()["blocked"] is False


class TestFirewallLogs:
    def test_logs_populated_after_check(self, client: TestClient) -> None:
        _create_rule(client, pattern="https://evil.example.com/*", action="deny")
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://evil.example.com/data", "agent_id": "agent-1"},
        )
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://safe.example.com/ok", "agent_id": "agent-2"},
        )
        resp = client.get("/api/v1/firewall/logs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_logs_filter_by_agent_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://example.com/a", "agent_id": "agent-x"},
        )
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://example.com/b", "agent_id": "agent-y"},
        )
        resp = client.get("/api/v1/firewall/logs", params={"agent_id": "agent-x"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["agent_id"] == "agent-x"

    def test_logs_filter_by_blocked(self, client: TestClient) -> None:
        _create_rule(client, pattern="https://evil.example.com/*", action="deny")
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://evil.example.com/bad", "agent_id": "agent-1"},
        )
        client.post(
            "/api/v1/firewall/check",
            json={"url": "https://safe.example.com/ok", "agent_id": "agent-2"},
        )
        resp = client.get("/api/v1/firewall/logs", params={"blocked": True})
        assert resp.status_code == 200
        logs = resp.json()
        assert all(log["blocked"] is True for log in logs)
