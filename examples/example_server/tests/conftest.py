"""Pytest configuration and fixtures for example_server tests."""

import pytest
import httpx
from unittest.mock import AsyncMock, Mock

from mcp_server_core.config import ServerConfig
from mcp_server_core.abstractions import URLFetcher, FileOperations


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ServerConfig(
        server_name="test-example-server",
        environment="dev",
        transport="stdio",
        log_level="DEBUG",
        url_require_https=False,
        allowed_file_directories=["/tmp", "./data"],
    )


@pytest.fixture
async def http_client():
    """Create HTTP client for tests."""
    client = httpx.AsyncClient()
    yield client
    await client.aclose()


@pytest.fixture
def url_fetcher(http_client, test_config):
    """Create URLFetcher for tests."""
    return URLFetcher(http_client, test_config)


@pytest.fixture
def file_ops(test_config):
    """Create FileOperations for tests."""
    return FileOperations(test_config)


@pytest.fixture
def mock_context():
    """Create mock Context object."""
    ctx = Mock()
    ctx.info = AsyncMock()
    ctx.debug = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()
    return ctx
