"""Tests for web tools."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from tools.web_tools import WebTools


@pytest.fixture
def web_tools(url_fetcher):
    """Create WebTools instance."""
    return WebTools(url_fetcher)


@pytest.mark.asyncio
async def test_fetch_url(web_tools, mock_context):
    """Test fetching URL."""
    # Mock DNS resolution
    async def mock_addrinfo(*args, **kwargs):
        return [(2, 1, 6, '', ('93.184.216.34', 0))]

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", side_effect=mock_addrinfo):
        with patch.object(web_tools.fetcher.client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Hello, World!"
            mock_response.headers = {"content-type": "text/html"}
            mock_response.url = "https://example.com"
            mock_request.return_value = mock_response

            result = await web_tools.fetch_url("https://example.com", mock_context)

            assert result["url"] == "https://example.com"
            assert result["status_code"] == 200
            assert "Hello, World!" in result["content"]
            assert result["content_type"] == "text/html"

            # Verify logging
            mock_context.info.assert_called()


@pytest.mark.asyncio
async def test_fetch_url_with_long_content(web_tools, mock_context):
    """Test fetching URL with content truncation."""
    with patch.object(web_tools.fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        with patch.object(web_tools.fetcher, "_check_ssrf", new_callable=AsyncMock):
            long_content = "x" * 2000
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = long_content
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            result = await web_tools.fetch_url("https://example.com", mock_context)

            # Content should be truncated to 1000 chars + "..."
            assert len(result["content"]) == 1003  # 1000 + "..."
            assert result["content_length"] == 2000


@pytest.mark.asyncio
async def test_fetch_json(web_tools, mock_context):
    """Test fetching and parsing JSON."""
    with patch.object(web_tools.fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        with patch.object(web_tools.fetcher, "_check_ssrf", new_callable=AsyncMock):
            test_data = {"key": "value", "number": 42}
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = test_data
            mock_request.return_value = mock_response

            result = await web_tools.fetch_json("https://api.example.com", mock_context)

            assert result == test_data

            # Verify logging
            mock_context.info.assert_called()


@pytest.mark.asyncio
async def test_fetch_json_invalid_json(web_tools, mock_context):
    """Test fetching invalid JSON."""
    with patch.object(web_tools.fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        with patch.object(web_tools.fetcher, "_check_ssrf", new_callable=AsyncMock):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.raise_for_status = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_request.return_value = mock_response

            with pytest.raises(ValueError, match="Invalid JSON"):
                await web_tools.fetch_json("https://api.example.com", mock_context)


@pytest.mark.asyncio
async def test_fetch_url_error_handling(web_tools, mock_context):
    """Test error handling in fetch_url."""
    with patch.object(web_tools.fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            await web_tools.fetch_url("https://example.com", mock_context)
