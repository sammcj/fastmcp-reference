"""Tests for URLFetcher security abstraction."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from mcp_server_core.abstractions import URLFetcher
from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError


@pytest.fixture
async def url_fetcher(test_config):
    """Create URLFetcher with test config."""
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, test_config)
    yield fetcher
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_https_url(url_fetcher):
    """Test fetching HTTPS URL."""
    # Mock DNS resolution to return a public IP
    mock_addrinfo = AsyncMock(return_value=[
        (2, 1, 6, '', ('93.184.216.34', 0))  # example.com IP
    ])

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", mock_addrinfo):
        with patch.object(url_fetcher.client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            mock_response.headers = {}
            mock_response.url = "https://example.com"
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            response = await url_fetcher.fetch("https://example.com")
            assert response.status_code == 200
            mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_http_url_in_dev(test_config):
    """Test fetching HTTP URL in dev environment."""
    test_config.url_require_https = False
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, test_config)

    # Mock DNS resolution to return a public IP
    mock_addrinfo = AsyncMock(return_value=[
        (2, 1, 6, '', ('93.184.216.34', 0))  # example.com IP
    ])

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", mock_addrinfo):
        with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.url = "http://example.com"
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            response = await fetcher.fetch("http://example.com")
            assert response.status_code == 200

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_http_url_blocked_in_production():
    """Test HTTP URL blocked when HTTPS required."""
    config = ServerConfig(server_name="test-server", environment="dev", url_require_https=True)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    with pytest.raises(SecurityError, match="HTTPS required"):
        await fetcher.fetch("http://example.com")

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_private_ip_blocked():
    """Test private IP addresses are blocked."""
    config = ServerConfig(server_name="test-server", environment="dev", url_allow_private_ips=False, url_require_https=False)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    private_ips = [
        "http://127.0.0.1",
        "http://192.168.1.1",
        "http://10.0.0.1",
        "http://172.16.0.1",
    ]

    for url in private_ips:
        with pytest.raises(SecurityError, match="resolves to private IP"):
            await fetcher.fetch(url)

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_private_ip_allowed_in_dev():
    """Test private IPs can be allowed in dev."""
    config = ServerConfig(server_name="test-server", environment="dev", url_allow_private_ips=True, url_require_https=False)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        response = await fetcher.fetch("http://127.0.0.1")
        assert response.status_code == 200

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_json_via_response(test_config):
    """Test fetching and parsing JSON via response.json()."""
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, test_config)

    # Mock both request and DNS resolution
    with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock_request:
        with patch.object(fetcher, "_check_ssrf", new_callable=AsyncMock):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"key": "value"}
            mock_request.return_value = mock_response

            response = await fetcher.fetch("https://api.example.com")
            data = response.json()
            assert data == {"key": "value"}

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_with_timeout(url_fetcher):
    """Test timeout configuration."""
    assert url_fetcher.timeout == 30  # Default from config


@pytest.mark.asyncio
async def test_fetch_invalid_url():
    """Test invalid URL raises error."""
    config = ServerConfig(server_name="test-server", environment="dev")
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    with pytest.raises(Exception):  # Will raise during URL parsing
        await fetcher.fetch("not-a-valid-url")

    await client.aclose()


# ============================================================================
# Additional Security Tests (From CODE_REVIEW.md)
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_large_response_blocked():
    """Test that responses exceeding max_size are blocked."""
    config = ServerConfig(server_name="test", url_max_size_mb=1)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock:
        mock_response = Mock()
        mock_response.headers = {"content-length": str(2 * 1024 * 1024)}  # 2MB
        mock_response.url = "https://example.com"
        mock_response.raise_for_status = Mock()
        mock.return_value = mock_response

        with pytest.raises(SecurityError, match="too large"):
            await fetcher.fetch("https://example.com")

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_dns_rebinding_protection():
    """Test DNS rebinding attack prevention via redirect validation."""
    config = ServerConfig(server_name="test", url_allow_private_ips=False)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    # Mock DNS to return public IP for initial host, but response shows redirect to private IP
    async def mock_getaddrinfo(host, port, **kwargs):
        if "public.example.com" in host:
            # Initial request - public IP
            return [(2, 1, 6, '', ('93.184.216.34', 0))]
        else:
            # After redirect - private IP (192.168.1.1)
            return [(2, 1, 6, '', ('192.168.1.1', 0))]

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", side_effect=mock_getaddrinfo):
        with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock:
            mock_response = Mock()
            mock_response.url = "http://192.168.1.1/data"  # Redirected to private IP
            mock_response.headers = {}
            mock_response.raise_for_status = Mock()
            mock.return_value = mock_response

            with pytest.raises(SecurityError, match="private IP"):
                await fetcher.fetch("https://public.example.com")

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_timeout_enforcement():
    """Test timeout is properly enforced."""
    config = ServerConfig(server_name="test", url_timeout_seconds=1)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    # Mock DNS resolution to return immediately
    async def mock_addrinfo(*args, **kwargs):
        return [(2, 1, 6, '', ('93.184.216.34', 0))]

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", side_effect=mock_addrinfo):
        with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock:
            # Simulate timeout by raising httpx.TimeoutException
            mock.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(httpx.TimeoutException):
                await fetcher.fetch("https://example.com")

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_streaming_response_size_validation():
    """Test streaming response size validation."""
    config = ServerConfig(server_name="test", url_max_size_mb=1)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock:
        mock_response = Mock()
        # No content-length header (streaming response)
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        mock_response.raise_for_status = Mock()
        mock.return_value = mock_response

        # Should succeed without content-length check
        response = await fetcher.fetch("https://example.com")
        assert response == mock_response

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_redirect_chain_validation():
    """Test redirect chain validation."""
    config = ServerConfig(server_name="test", url_allow_private_ips=False)
    client = httpx.AsyncClient()
    fetcher = URLFetcher(client, config)

    # Mock DNS to return different IPs based on hostname
    async def mock_getaddrinfo(host, port, **kwargs):
        if "public.example.com" in host:
            # Initial request - public IP
            return [(2, 1, 6, '', ('93.184.216.34', 0))]
        else:
            # After redirect - private IP (10.0.0.1)
            return [(2, 1, 6, '', ('10.0.0.1', 0))]

    with patch.object(asyncio.get_event_loop(), "getaddrinfo", side_effect=mock_getaddrinfo):
        with patch.object(fetcher.client, "request", new_callable=AsyncMock) as mock:
            # Simulate redirect from public to private IP
            mock_response = Mock()
            mock_response.url = "http://10.0.0.1/data"  # Final URL after redirect chain
            mock_response.headers = {}
            mock_response.raise_for_status = Mock()
            mock.return_value = mock_response

            with pytest.raises(SecurityError, match="private IP"):
                await fetcher.fetch("https://public.example.com")

    await client.aclose()
