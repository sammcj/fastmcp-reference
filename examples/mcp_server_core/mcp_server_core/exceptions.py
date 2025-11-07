"""Custom exceptions for mcp_server_core."""

from fastmcp.exceptions import ToolError


class SecurityError(ToolError):
    """Raised when a security validation fails.

    This extends ToolError so security violations are always
    communicated to the client clearly, regardless of error masking settings.

    Examples:
        - SSRF prevention (private IP access)
        - Path traversal detection
        - File size limits exceeded
    """

    pass
