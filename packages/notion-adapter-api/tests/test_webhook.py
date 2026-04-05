"""Tests for webhook parsing and signature verification."""

import hashlib
import hmac

from lintel.notion_adapter_api.webhook import parse_webhook_event, verify_signature


class TestVerifySignature:
    def test_valid_signature(self) -> None:
        body = b'{"type": "page.updated"}'
        secret = "test-secret"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_signature(body, sig, secret) is True

    def test_invalid_signature(self) -> None:
        body = b'{"type": "page.updated"}'
        assert verify_signature(body, "bad-sig", "test-secret") is False

    def test_empty_signature(self) -> None:
        body = b'{"type": "page.updated"}'
        assert verify_signature(body, "", "test-secret") is False

    def test_tampered_body(self) -> None:
        secret = "test-secret"
        original = b'{"type": "page.updated"}'
        sig = hmac.new(secret.encode(), original, hashlib.sha256).hexdigest()
        tampered = b'{"type": "page.deleted"}'
        assert verify_signature(tampered, sig, secret) is False


class TestParseWebhookEvent:
    def test_parse_page_updated(self) -> None:
        payload = {"type": "page.updated", "data": {"id": "page-1"}}
        result = parse_webhook_event(payload)
        assert result["event_type"] == "page.updated"
        assert result["page_id"] == "page-1"

    def test_parse_empty_payload(self) -> None:
        result = parse_webhook_event({})
        assert result["event_type"] == "unknown"
        assert result["page_id"] == ""
        assert result["database_id"] == ""

    def test_parse_extracts_database_id_from_parent(self) -> None:
        payload = {
            "type": "page.updated",
            "data": {
                "id": "page-42",
                "parent": {"database_id": "db-abc123"},
            },
        }
        result = parse_webhook_event(payload)
        assert result["database_id"] == "db-abc123"
        assert result["page_id"] == "page-42"

    def test_parse_no_parent(self) -> None:
        payload = {"type": "page.created", "data": {"id": "page-99"}}
        result = parse_webhook_event(payload)
        assert result["database_id"] == ""

    def test_parse_parent_without_database_id(self) -> None:
        payload = {
            "type": "page.updated",
            "data": {"id": "page-1", "parent": {"workspace": True}},
        }
        result = parse_webhook_event(payload)
        assert result["database_id"] == ""
