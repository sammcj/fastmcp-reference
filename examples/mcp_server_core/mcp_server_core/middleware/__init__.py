"""Middleware implementations for mcp_server_core.

This module provides custom middleware for MCP servers beyond what FastMCP provides:
- SecurityAuditMiddleware: Audit logging for security-sensitive operations
- PerClientRateLimitMiddleware: Per-client rate limiting to prevent abuse

For built-in FastMCP middleware, import directly from fastmcp.server.middleware.
"""

from mcp_server_core.middleware.audit import SecurityAuditMiddleware
from mcp_server_core.middleware.rate_limit import PerClientRateLimitMiddleware

__all__ = ["SecurityAuditMiddleware", "PerClientRateLimitMiddleware"]
