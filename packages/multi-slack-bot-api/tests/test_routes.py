"""Tests for multi-slack-bot API."""

import hashlib
import hmac
import time

from fastapi.testclient import TestClient


def _make_signature(signing_secret: str, timestamp: str, body: str) -> str:
    sig_basestring = f"v0:{timestamp}:{body}"
    return (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )


class TestSlackBotsAPI:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-1",
                "name": "My Bot",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-test",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "bot-1"
        assert data["name"] == "My Bot"
        assert data["enabled"] is True

    def test_create_with_signing_secret_masks_in_response(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-sec",
                "name": "Secure Bot",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-test",
                "signing_secret": "my-secret-123",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["signing_secret"] == "***"

    def test_create_with_project_and_workflow_bindings(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-bind",
                "name": "Scoped Bot",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-test",
                "project_bindings": ["proj-1", "proj-2"],
                "workflow_bindings": ["wf-1"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_bindings"] == ["proj-1", "proj-2"]
        assert data["workflow_bindings"] == ["wf-1"]

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "bot_id": "bot-dup",
            "name": "Dup",
            "workspace_id": "ws-1",
            "bot_token": "xoxb-test",
        }
        client.post("/api/v1/slack-bots", json=body)
        resp = client.post("/api/v1/slack-bots", json=body)
        assert resp.status_code == 409

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack-bots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-2",
                "name": "B2",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        resp = client.get("/api/v1/slack-bots")
        assert len(resp.json()) == 1

    def test_list_filter_by_workspace_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "b1",
                "name": "B1",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "b2",
                "name": "B2",
                "workspace_id": "ws-2",
                "bot_token": "t",
            },
        )
        resp = client.get("/api/v1/slack-bots", params={"workspace_id": "ws-1"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["workspace_id"] == "ws-1"

    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-3",
                "name": "B3",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        resp = client.get("/api/v1/slack-bots/bot-3")
        assert resp.status_code == 200
        assert resp.json()["bot_id"] == "bot-3"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack-bots/nonexistent")
        assert resp.status_code == 404

    def test_patch_updates_fields(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-4",
                "name": "Old",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        resp = client.patch(
            "/api/v1/slack-bots/bot-4",
            json={"name": "New", "enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"
        assert resp.json()["enabled"] is False

    def test_patch_project_bindings(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-pb",
                "name": "PB",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        resp = client.patch(
            "/api/v1/slack-bots/bot-pb",
            json={"project_bindings": ["p1"]},
        )
        assert resp.status_code == 200
        assert resp.json()["project_bindings"] == ["p1"]

    def test_patch_missing_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/slack-bots/missing", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_existing_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-5",
                "name": "B5",
                "workspace_id": "ws-1",
                "bot_token": "t",
            },
        )
        resp = client.delete("/api/v1/slack-bots/bot-5")
        assert resp.status_code == 204
        assert client.get("/api/v1/slack-bots/bot-5").status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/slack-bots/nonexistent")
        assert resp.status_code == 404


class TestSlackBotWebhook:
    def test_url_verification_challenge(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots/webhook",
            json={"type": "url_verification", "challenge": "abc123"},
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "abc123"

    def test_webhook_routes_to_correct_bot(self, client: TestClient) -> None:
        secret_a = "secret-alpha"
        secret_b = "secret-beta"
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-a",
                "name": "Alpha",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-a",
                "signing_secret": secret_a,
            },
        )
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-b",
                "name": "Beta",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-b",
                "signing_secret": secret_b,
            },
        )

        body = '{"event":{"type":"message","text":"hello"}}'
        timestamp = str(int(time.time()))
        sig = _make_signature(secret_b, timestamp, body)

        resp = client.post(
            "/api/v1/slack-bots/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": sig,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == "bot-b"
        assert data["bot_name"] == "Beta"

    def test_webhook_rejects_invalid_signature(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-x",
                "name": "X",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-x",
                "signing_secret": "real-secret",
            },
        )

        body = '{"event":{"type":"message"}}'
        timestamp = str(int(time.time()))
        sig = _make_signature("wrong-secret", timestamp, body)

        resp = client.post(
            "/api/v1/slack-bots/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": sig,
            },
        )
        assert resp.status_code == 401

    def test_webhook_skips_disabled_bot(self, client: TestClient) -> None:
        secret = "bot-disabled-secret"
        client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-dis",
                "name": "Disabled",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-dis",
                "signing_secret": secret,
            },
        )
        client.patch("/api/v1/slack-bots/bot-dis", json={"enabled": False})

        body = '{"event":{"type":"message"}}'
        timestamp = str(int(time.time()))
        sig = _make_signature(secret, timestamp, body)

        resp = client.post(
            "/api/v1/slack-bots/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": sig,
            },
        )
        assert resp.status_code == 401

    def test_webhook_invalid_json(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots/webhook",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
