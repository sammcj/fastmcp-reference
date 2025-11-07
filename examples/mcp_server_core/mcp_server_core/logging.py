"""Transport-aware logging configuration for MCP servers.

CRITICAL: STDIO mode CANNOT log to stdout/stderr (reserved for MCP protocol).

This module configures Python's logging system based on transport mode:
- STDIO: Logs to file (default: /tmp/mcp-{server_name}.log)
- HTTP: Logs to stdout (captured by container runtime)

Uses FastMCP's built-in StructuredLoggingMiddleware for JSON output.
"""

import logging
from pathlib import Path

from fastmcp.server.middleware.logging import StructuredLoggingMiddleware

from mcp_server_core.config import ServerConfig


def configure_logging(config: ServerConfig) -> StructuredLoggingMiddleware:
    """Configure transport-aware logging using FastMCP's built-in middleware.

    CRITICAL: STDIO mode logs to file (stdout/stderr reserved for protocol).
    HTTP mode logs to stdout (captured by container runtime).

    Args:
        config: Server configuration

    Returns:
        Configured StructuredLoggingMiddleware instance

    Example:
        >>> config = ServerConfig()
        >>> logging_middleware = configure_logging(config)
        >>> mcp.add_middleware(logging_middleware)
    """

    # Configure Python's logging based on transport
    if config.transport == "stdio":
        # STDIO mode: log to file (stdout/stderr reserved for MCP protocol)
        log_path = Path(config.log_file or f"/tmp/mcp-{config.server_name}.log")

        # Create directory and validate writability
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(f"Cannot create log directory: {log_path.parent}") from e

        # Test file is writable
        try:
            with log_path.open("a"):
                pass
        except PermissionError as e:
            raise RuntimeError(f"Log file not writable: {log_path}") from e

        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(message)s",  # JSON from StructuredLoggingMiddleware
            handlers=[logging.FileHandler(str(log_path), mode="a")],
            force=True,  # Override any existing configuration
        )

        # Log the file location at startup
        logger = logging.getLogger(__name__)
        logger.info(f"STDIO mode: Logging to file {log_path}")

    else:
        # HTTP mode: log to stdout (captured by container runtime)
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(message)s",  # JSON from StructuredLoggingMiddleware
            handlers=[
                logging.StreamHandler()  # stdout
            ],
            force=True,
        )

    # Return FastMCP's structured logging middleware
    return StructuredLoggingMiddleware(include_payloads=config.log_include_payloads)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    This is a convenience function for getting loggers in server core code.
    Tools should use Context logging methods (ctx.info, ctx.error, etc.) instead.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Server initialisation complete")
    """
    return logging.getLogger(name)
