"""MCP Server Core: Reusable components for building production-ready MCP servers.

This package provides:
- Transport-aware logging (STDIO vs HTTP)
- Type-safe configuration management
- Security abstractions (SSRF prevention, path traversal protection)
- Optional observability (OpenTelemetry, Prometheus)
- Middleware configuration helpers

All built on top of FastMCP's excellent built-in features.
"""

from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError
from mcp_server_core.server import MCPServer

__version__ = "0.1.0"

__all__ = [
    "ServerConfig",
    "MCPServer",
    "SecurityError",
]
