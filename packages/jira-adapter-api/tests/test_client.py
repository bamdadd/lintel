"""Tests for JiraClient."""

from __future__ import annotations

from lintel.jira_adapter_api.client import _extract_text, _parse_issue


class TestParseIssue:
    def test_parse_minimal(self) -> None:
        data = {
            "key": "EX-1",
            "fields": {
                "summary": "Test issue",
                "status": {"name": "To Do"},
                "issuetype": {"name": "Task"},
            },
        }
        issue = _parse_issue(data)
        assert issue.key == "EX-1"
        assert issue.summary == "Test issue"
        assert issue.status == "To Do"
        assert issue.issue_type == "Task"
        assert issue.assignee is None

    def test_parse_with_assignee(self) -> None:
        data = {
            "key": "EX-2",
            "fields": {
                "summary": "Assigned",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Alice"},
            },
        }
        issue = _parse_issue(data)
        assert issue.assignee == "Alice"


class TestExtractText:
    def test_empty(self) -> None:
        assert _extract_text(None) == ""
        assert _extract_text({}) == ""

    def test_simple_doc(self) -> None:
        doc = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                },
            ],
        }
        assert _extract_text(doc) == "Hello world"
