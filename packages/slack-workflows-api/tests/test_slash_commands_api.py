"""Tests for the /slack/commands endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _post_command(client: TestClient, text: str = "") -> dict:
    resp = client.post(
        "/api/v1/slack/commands",
        data={
            "command": "/lintel",
            "text": text,
            "user_id": "U123",
            "channel_id": "C456",
        },
    )
    assert resp.status_code == 200
    return resp.json()


class TestSlashCommandEndpoint:
    def test_help_command(self, client: TestClient) -> None:
        data = _post_command(client, "help")
        assert data["response_type"] == "ephemeral"
        assert any("/lintel board" in b.get("text", {}).get("text", "") for b in data["blocks"])

    def test_empty_defaults_to_help(self, client: TestClient) -> None:
        data = _post_command(client, "")
        assert data["response_type"] == "ephemeral"
        assert data["blocks"][0]["type"] == "header"

    def test_board_empty(self, client: TestClient) -> None:
        data = _post_command(client, "board")
        assert data["response_type"] == "ephemeral"
        assert len(data["blocks"]) >= 1

    def test_board_with_items(self, client: TestClient) -> None:
        # Create a work item first
        client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "wi-slash1",
                "title": "Test slash board",
                "status": "open",
                "work_type": "feature",
                "project_id": "proj-1",
            },
        )
        data = _post_command(client, "board")
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "Test slash board" in block_texts

    def test_status_found(self, client: TestClient) -> None:
        client.post(
            "/api/v1/work-items",
            json={
                "work_item_id": "wi-status1",
                "title": "Status test item",
                "status": "in_progress",
                "work_type": "bug",
                "project_id": "proj-1",
            },
        )
        data = _post_command(client, "status wi-status1")
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "Status test item" in block_texts
        assert "in_progress" in block_texts

    def test_status_not_found(self, client: TestClient) -> None:
        data = _post_command(client, "status wi-missing")
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "not found" in block_texts.lower()

    def test_status_no_args(self, client: TestClient) -> None:
        data = _post_command(client, "status")
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "usage" in block_texts.lower() or "Usage" in block_texts

    def test_create_work_item(self, client: TestClient) -> None:
        data = _post_command(client, "create bug Fix login timeout")
        assert data["response_type"] == "in_channel"
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "Fix login timeout" in block_texts
        assert "bug" in block_texts

    def test_create_without_type(self, client: TestClient) -> None:
        data = _post_command(client, "create Add dark mode")
        assert data["response_type"] == "in_channel"
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "Add dark mode" in block_texts

    def test_create_no_title(self, client: TestClient) -> None:
        data = _post_command(client, "create")
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "usage" in block_texts.lower() or "Usage" in block_texts

    def test_unknown_command(self, client: TestClient) -> None:
        data = _post_command(client, "foobar")
        assert data["response_type"] == "ephemeral"
        block_texts = " ".join(b.get("text", {}).get("text", "") for b in data["blocks"])
        assert "unknown" in block_texts.lower() or "foobar" in block_texts


def _post_interaction(client: TestClient, payload: dict) -> dict:
    import json

    resp = client.post(
        "/api/v1/slack/interactions",
        data={"payload": json.dumps(payload)},
    )
    assert resp.status_code == 200
    return resp.json()


class TestSlackInteractionsEndpoint:
    def test_view_submission_creates_work_item(self, client: TestClient) -> None:
        payload = {
            "type": "view_submission",
            "view": {
                "callback_id": "create_work_item",
                "private_metadata": "proj-1",
                "state": {
                    "values": {
                        "title_block": {"title_input": {"value": "New feature via modal"}},
                        "description_block": {
                            "description_input": {"value": "Detailed description"}
                        },
                        "type_block": {"type_select": {"selected_option": {"value": "feature"}}},
                    }
                },
            },
        }
        result = _post_interaction(client, payload)
        # Empty response = modal closes successfully
        assert result == {}

        # Verify work item was created
        items = client.get("/api/v1/work-items").json()
        matching = [i for i in items if i["title"] == "New feature via modal"]
        assert len(matching) == 1
        assert matching[0]["work_type"] == "feature"
        assert matching[0]["description"] == "Detailed description"
        assert matching[0]["project_id"] == "proj-1"

    def test_view_submission_rejects_empty_title(self, client: TestClient) -> None:
        payload = {
            "type": "view_submission",
            "view": {
                "callback_id": "create_work_item",
                "state": {
                    "values": {
                        "title_block": {"title_input": {"value": "  "}},
                        "description_block": {"description_input": {"value": ""}},
                        "type_block": {"type_select": {"selected_option": {"value": "task"}}},
                    }
                },
            },
        }
        result = _post_interaction(client, payload)
        assert result.get("response_action") == "errors"
        assert "title_block" in result.get("errors", {})

    def test_view_submission_bug_type(self, client: TestClient) -> None:
        payload = {
            "type": "view_submission",
            "view": {
                "callback_id": "create_work_item",
                "state": {
                    "values": {
                        "title_block": {"title_input": {"value": "Fix crash on login"}},
                        "description_block": {"description_input": {"value": None}},
                        "type_block": {"type_select": {"selected_option": {"value": "bug"}}},
                    }
                },
            },
        }
        result = _post_interaction(client, payload)
        assert result == {}

        items = client.get("/api/v1/work-items").json()
        matching = [i for i in items if i["title"] == "Fix crash on login"]
        assert len(matching) == 1
        assert matching[0]["work_type"] == "bug"

    def test_unknown_callback_id(self, client: TestClient) -> None:
        payload = {
            "type": "view_submission",
            "view": {"callback_id": "unknown_modal", "state": {"values": {}}},
        }
        result = _post_interaction(client, payload)
        assert result == {}

    def test_empty_payload(self, client: TestClient) -> None:
        resp = client.post("/api/v1/slack/interactions", data={"payload": ""})
        assert resp.status_code == 200
