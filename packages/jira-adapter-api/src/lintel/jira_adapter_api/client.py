"""Jira REST API client wrapper."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from lintel.jira_adapter_api.types import JiraIssue

logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    """Raised when a Jira API call fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Jira API error {status_code}: {detail}")


class JiraClient:
    """Thin wrapper around Jira REST API v3."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(email, api_token)
        self._timeout = timeout

    async def get_issue(self, issue_key: str) -> JiraIssue:
        """Fetch a single issue by key."""
        url = f"{self._base_url}/rest/api/3/issue/{issue_key}"
        async with httpx.AsyncClient(auth=self._auth, timeout=self._timeout) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise JiraClientError(resp.status_code, resp.text)
        return _parse_issue(resp.json())

    async def search_issues(
        self,
        jql: str,
        *,
        max_results: int = 50,
    ) -> list[JiraIssue]:
        """Search issues using JQL."""
        url = f"{self._base_url}/rest/api/3/search"
        params: dict[str, Any] = {"jql": jql, "maxResults": max_results}
        async with httpx.AsyncClient(auth=self._auth, timeout=self._timeout) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise JiraClientError(resp.status_code, resp.text)
        data = resp.json()
        return [_parse_issue(i) for i in data.get("issues", [])]

    async def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """Transition an issue to a new status."""
        url = f"{self._base_url}/rest/api/3/issue/{issue_key}/transitions"
        body = {"transition": {"id": transition_id}}
        async with httpx.AsyncClient(auth=self._auth, timeout=self._timeout) as client:
            resp = await client.post(url, json=body)
        if resp.status_code not in (200, 204):
            raise JiraClientError(resp.status_code, resp.text)

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str = "",
    ) -> str:
        """Create an issue and return its key."""
        url = f"{self._base_url}/rest/api/3/issue"
        body: dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            },
        }
        if description:
            body["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    },
                ],
            }
        async with httpx.AsyncClient(auth=self._auth, timeout=self._timeout) as client:
            resp = await client.post(url, json=body)
        if resp.status_code not in (200, 201):
            raise JiraClientError(resp.status_code, resp.text)
        return str(resp.json()["key"])


def _parse_issue(data: dict[str, Any]) -> JiraIssue:
    """Parse a Jira API issue response into a JiraIssue."""
    fields = data.get("fields", {})
    assignee = fields.get("assignee")
    return JiraIssue(
        key=data["key"],
        summary=fields.get("summary", ""),
        status=(fields.get("status") or {}).get("name", ""),
        issue_type=(fields.get("issuetype") or {}).get("name", ""),
        description=_extract_text(fields.get("description")),
        assignee=assignee.get("displayName") if assignee else None,
        updated=fields.get("updated", ""),
    )


def _extract_text(doc: Any) -> str:  # noqa: ANN401
    """Extract plain text from Atlassian Document Format."""
    if not doc or not isinstance(doc, dict):
        return ""
    parts: list[str] = []
    for block in doc.get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                parts.append(str(inline.get("text", "")))
    return " ".join(parts)
