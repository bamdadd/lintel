"""Tests for NotionClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.notion_adapter_api.client import NotionClient


class TestNotionClient:
    def test_headers_include_auth(self) -> None:
        client = NotionClient(api_key="ntn_secret")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer ntn_secret"
        assert "Notion-Version" in headers

    @pytest.mark.asyncio
    async def test_query_database_calls_api(self) -> None:
        client = NotionClient(api_key="ntn_secret")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": [], "has_more": False}
        mock_resp.raise_for_status = MagicMock()

        with patch("lintel.notion_adapter_api.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.query_database("db-123")
            assert result == {"results": [], "has_more": False}
            mock_http.post.assert_called_once()
