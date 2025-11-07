"""Security audit logging middleware for compliance and debugging."""

import logging
from datetime import datetime, timezone

from fastmcp.server.middleware import Middleware, MiddlewareContext

audit_logger = logging.getLogger("mcp.security.audit")


class SecurityAuditMiddleware(Middleware):
    """Log all security-relevant events for compliance and debugging.

    This middleware logs security-sensitive operations including:
    - File operations (read, write, delete, list)
    - URL fetching (HTTP requests)
    - Tool invocations on security-sensitive tools

    Logs include:
    - Event type (invocation, completion, failure)
    - Tool name
    - Sanitised parameters (sensitive data removed)
    - Timestamp
    - Success/failure status
    - Error details (on failure)

    Example:
        >>> from mcp_server_core.middleware import SecurityAuditMiddleware
        >>> from mcp_server_core import MCPServer, ServerConfig
        >>>
        >>> config = ServerConfig()
        >>> mcp_server = MCPServer(config)
        >>> mcp_server.mcp.add_middleware(SecurityAuditMiddleware())
    """

    SECURITY_SENSITIVE_TOOLS = {
        "fetch_url",
        "fetch_json",
        "read_file",
        "write_file",
        "delete_file",
        "list_directory",
    }

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Log security-sensitive tool invocations."""
        tool_name = context.message.name

        if tool_name in self.SECURITY_SENSITIVE_TOOLS:
            audit_logger.warning(
                "Security-sensitive tool invoked",
                extra={
                    "event": "tool_invocation",
                    "tool": tool_name,
                    "params": self._sanitise_params(context.message.arguments),
                    "source": context.source or "unknown",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        try:
            result = await call_next(context)

            if tool_name in self.SECURITY_SENSITIVE_TOOLS:
                audit_logger.info(
                    "Security-sensitive tool completed",
                    extra={
                        "event": "tool_completion",
                        "tool": tool_name,
                        "status": "success",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            return result

        except Exception as e:
            if tool_name in self.SECURITY_SENSITIVE_TOOLS:
                audit_logger.error(
                    "Security-sensitive tool failed",
                    extra={
                        "event": "tool_failure",
                        "tool": tool_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            raise

    def _sanitise_params(self, params: dict) -> dict:
        """Remove sensitive data from params before logging.

        Args:
            params: Tool parameters

        Returns:
            Sanitised parameters with sensitive data removed
        """
        if not params:
            return {}

        sanitised = params.copy()

        # Remove content from write operations to avoid logging sensitive data
        if "content" in sanitised:
            content_size = len(str(sanitised["content"]))
            sanitised["content"] = f"<{content_size} bytes>"

        # Sanitise headers (may contain auth tokens)
        if "headers" in sanitised and isinstance(sanitised["headers"], dict):
            sanitised_headers = {}
            for key, value in sanitised["headers"].items():
                if key.lower() in ("authorization", "cookie", "x-api-key"):
                    sanitised_headers[key] = "<redacted>"
                else:
                    sanitised_headers[key] = value
            sanitised["headers"] = sanitised_headers

        return sanitised
