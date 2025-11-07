"""Tests for SecurityAuditMiddleware."""

import logging
from unittest.mock import MagicMock

import pytest
from fastmcp import Client

from mcp_server_core.config import ServerConfig
from mcp_server_core.middleware.audit import SecurityAuditMiddleware
from mcp_server_core.server import MCPServer


@pytest.fixture
def audit_logger_mock(monkeypatch):
    """Mock the audit logger to capture log calls."""
    mock_logger = MagicMock(spec=logging.Logger)
    monkeypatch.setattr("mcp_server_core.middleware.audit.audit_logger", mock_logger)
    return mock_logger


@pytest.mark.asyncio
async def test_security_audit_logs_sensitive_tool_invocation(audit_logger_mock):
    """Test audit middleware logs security-sensitive tool calls."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    # Add audit middleware
    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def fetch_url(url: str) -> str:
        """Security-sensitive tool."""
        return f"Fetched: {url}"

    async with Client(mcp_server.mcp) as client:
        await client.call_tool("fetch_url", {"url": "https://example.com"})

    # Check that warning was logged for invocation
    assert audit_logger_mock.warning.called
    call_args = audit_logger_mock.warning.call_args
    assert "Security-sensitive tool invoked" in call_args[0][0]
    assert call_args[1]["extra"]["tool"] == "fetch_url"
    assert call_args[1]["extra"]["event"] == "tool_invocation"


@pytest.mark.asyncio
async def test_security_audit_logs_tool_completion(audit_logger_mock):
    """Test audit middleware logs successful tool completion."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def read_file(file_path: str) -> str:
        """Security-sensitive tool."""
        return "file contents"

    async with Client(mcp_server.mcp) as client:
        await client.call_tool("read_file", {"file_path": "/tmp/test.txt"})

    # Check that info was logged for completion
    assert audit_logger_mock.info.called
    call_args = audit_logger_mock.info.call_args
    assert "Security-sensitive tool completed" in call_args[0][0]
    assert call_args[1]["extra"]["tool"] == "read_file"
    assert call_args[1]["extra"]["status"] == "success"


@pytest.mark.asyncio
async def test_security_audit_logs_tool_failure(audit_logger_mock):
    """Test audit middleware logs tool failures."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def write_file(file_path: str, content: str) -> str:
        """Security-sensitive tool that fails."""
        raise ValueError("Simulated error")

    async with Client(mcp_server.mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("write_file", {"file_path": "/tmp/test.txt", "content": "data"})

    # Check that error was logged for failure
    # Note: FastMCP wraps exceptions in ToolError, so error_type will be ToolError
    assert audit_logger_mock.error.called
    call_args = audit_logger_mock.error.call_args
    assert "Security-sensitive tool failed" in call_args[0][0]
    assert call_args[1]["extra"]["tool"] == "write_file"
    assert call_args[1]["extra"]["error_type"] == "ToolError"
    # Error message contains tool name and generic error message
    assert "write_file" in call_args[1]["extra"]["error"]


@pytest.mark.asyncio
async def test_security_audit_sanitises_content_parameter(audit_logger_mock):
    """Test audit middleware sanitises content in write operations."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def write_file(file_path: str, content: str) -> str:
        """Tool with sensitive content."""
        return "written"

    async with Client(mcp_server.mcp) as client:
        await client.call_tool("write_file", {"file_path": "/tmp/test.txt", "content": "sensitive data"})

    # Check that content was sanitised
    warning_call = audit_logger_mock.warning.call_args
    params = warning_call[1]["extra"]["params"]
    assert "content" in params
    assert "bytes" in params["content"]  # Should be sanitised to size
    assert "sensitive data" not in str(params)  # Original content should not be logged


@pytest.mark.asyncio
async def test_security_audit_sanitises_auth_headers(audit_logger_mock):
    """Test audit middleware sanitises authorisation headers."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def fetch_url(url: str, headers: dict) -> str:
        """Tool with headers."""
        return "fetched"

    async with Client(mcp_server.mcp) as client:
        await client.call_tool(
            "fetch_url",
            {"url": "https://example.com", "headers": {"Authorization": "Bearer secret-token", "Content-Type": "application/json"}},
        )

    # Check that auth headers were sanitised
    warning_call = audit_logger_mock.warning.call_args
    params = warning_call[1]["extra"]["params"]
    assert params["headers"]["Authorization"] == "<redacted>"
    assert params["headers"]["Content-Type"] == "application/json"  # Non-sensitive header preserved


@pytest.mark.asyncio
async def test_security_audit_ignores_non_sensitive_tools(audit_logger_mock):
    """Test audit middleware doesn't log non-sensitive tools."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    def calculate_total(items: list) -> float:
        """Non-sensitive tool."""
        return sum(items)

    async with Client(mcp_server.mcp) as client:
        await client.call_tool("calculate_total", {"items": [1, 2, 3]})

    # Check that audit logger was NOT called for non-sensitive tool
    assert not audit_logger_mock.warning.called
    assert not audit_logger_mock.info.called
    assert not audit_logger_mock.error.called


@pytest.mark.asyncio
async def test_security_audit_includes_timestamp(audit_logger_mock):
    """Test audit middleware includes timestamp in logs."""
    config = ServerConfig(server_name="test", environment="dev")
    mcp_server = MCPServer(config)

    mcp_server.mcp.add_middleware(SecurityAuditMiddleware())

    @mcp_server.mcp.tool
    async def delete_file(file_path: str) -> str:
        """Security-sensitive tool."""
        return "deleted"

    async with Client(mcp_server.mcp) as client:
        await client.call_tool("delete_file", {"file_path": "/tmp/test.txt"})

    # Check that timestamp is included
    warning_call = audit_logger_mock.warning.call_args
    assert "timestamp" in warning_call[1]["extra"]
    assert warning_call[1]["extra"]["timestamp"]  # Should be non-empty
