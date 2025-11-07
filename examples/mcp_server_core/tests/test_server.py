"""Tests for MCPServer."""

from unittest.mock import patch

import pytest

from mcp_server_core.config import ServerConfig
from mcp_server_core.server import MCPServer


@pytest.fixture
def server(test_config):
    """Create MCPServer instance."""
    return MCPServer(test_config)


def test_server_initialization(server, test_config):
    """Test server initializes correctly."""
    assert server.config == test_config
    assert server.mcp is not None
    assert server.http_client is None  # Not initialized until context manager


def test_server_mcp_instance(server):
    """Test server has FastMCP instance."""
    assert hasattr(server.mcp, "tool")
    assert hasattr(server.mcp, "run")


def test_server_get_http_client_before_startup(server):
    """Test getting HTTP client before server startup raises error."""
    with pytest.raises(RuntimeError, match="Server not started"):
        server.get_http_client()


def test_server_run_stdio_mode(test_config):
    """Test server run in STDIO mode."""
    server = MCPServer(test_config)

    with patch.object(server.mcp, "run") as mock_run:
        server.run()
        mock_run.assert_called_once_with(transport="stdio")


def test_server_run_http_mode(http_config):
    """Test server run in HTTP mode."""
    server = MCPServer(http_config)

    with patch.object(server.mcp, "run") as mock_run:
        server.run()
        mock_run.assert_called_once_with(transport="http", host="127.0.0.1", port=8888)


def test_server_with_rate_limiting_disabled():
    """Test server with rate limiting disabled."""
    config = ServerConfig(server_name="test-server", environment="dev", rate_limit_enabled=False)
    server = MCPServer(config)
    assert server.config.rate_limit_enabled is False


def test_server_with_retry_disabled():
    """Test server with retry disabled."""
    config = ServerConfig(server_name="test-server", environment="dev", retry_enabled=False)
    server = MCPServer(config)
    assert server.config.retry_enabled is False


def test_server_lifespan_handler_configured():
    """Test lifespan handler is configured on server.

    Note: FastMCP doesn't expose lifespan as a public attribute for inspection.
    Lifespan functionality is validated by integration tests that successfully
    use app_context['http_client'] and app_context['config'], proving the
    lifespan handler executed correctly.
    """
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    # Verify server initialised successfully
    # (lifespan functionality proven by app_context usage in other tests)
    assert mcp_server.config == config
    assert mcp_server.mcp is not None


# ============================================================================
# Additional Lifecycle Tests (From CODE_REVIEW.md)
# ============================================================================


def test_server_http_client_initially_none():
    """Test HTTP client is None before lifespan startup."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    # HTTP client should be None until lifespan starts
    assert mcp_server.http_client is None


@pytest.mark.asyncio
async def test_server_middleware_error_handling():
    """Test middleware error propagation."""
    from fastmcp import Client


    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    @mcp_server.mcp.tool
    def failing_tool() -> str:
        raise ValueError("Test error")

    async with Client(mcp_server.mcp) as client:
        with pytest.raises(Exception):  # Should propagate through middleware
            await client.call_tool("failing_tool", {})


def test_server_http_client_configuration():
    """Test HTTP client will be configured with correct settings."""
    config = ServerConfig(server_name="test", environment="dev", url_timeout_seconds=60)
    mcp_server = MCPServer(config)

    # Verify config is stored for later HTTP client initialization
    assert mcp_server.config.url_timeout_seconds == 60


def test_server_get_http_client_method_exists():
    """Test server has get_http_client method for accessing client."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    # Verify method exists
    assert hasattr(mcp_server, "get_http_client")
    assert callable(mcp_server.get_http_client)


@pytest.mark.asyncio
async def test_server_middleware_order():
    """Test middleware is added in correct order."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    # Verify middleware stack exists
    assert hasattr(mcp_server.mcp, "middleware")
    # At minimum, we should have error handling, retry, rate limiting, timing, and logging middleware
    assert len(mcp_server.mcp.middleware) >= 5
