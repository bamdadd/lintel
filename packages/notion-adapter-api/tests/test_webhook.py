"""Tests for webhook parsing utilities."""

from lintel.notion_adapter_api.webhook import parse_webhook_event


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
