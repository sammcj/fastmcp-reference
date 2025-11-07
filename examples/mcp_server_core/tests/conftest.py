"""Pytest configuration and fixtures for mcp_server_core tests."""

import pytest

from mcp_server_core.config import ServerConfig


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ServerConfig(
        server_name="test-server",
        environment="dev",
        transport="stdio",
        log_level="DEBUG",
        url_require_https=False,  # Allow HTTP in tests
        mask_error_details=False,  # Show full errors in tests
        include_traceback=True,
    )


@pytest.fixture
def http_config():
    """Create HTTP transport configuration."""
    return ServerConfig(
        server_name="test-http-server",
        environment="dev",
        transport="http",
        log_level="DEBUG",
        http_host="127.0.0.1",
        http_port=8888,
        url_require_https=False,
        mask_error_details=False,
        include_traceback=True,
    )
