"""MCP server creation with pre-configured middleware stack."""

from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware,
    RetryMiddleware,
)
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware

from mcp_server_core.config import ServerConfig
from mcp_server_core.logging import configure_logging, get_logger

logger = get_logger(__name__)


class MCPServer:
    """MCP server with pre-configured middleware stack.

    This class wraps FastMCP and automatically configures:
    - Transport-aware logging (STDIO file-based, HTTP stdout)
    - Error handling and retry middleware
    - Rate limiting
    - Detailed timing/performance monitoring
    - Optional observability (OpenTelemetry, Prometheus)

    Example:
        >>> from mcp_server_core import ServerConfig, MCPServer
        >>>
        >>> config = ServerConfig()
        >>> mcp_server = MCPServer(config)
        >>>
        >>> @mcp_server.mcp.tool
        >>> def my_tool(data: str) -> str:
        ...     return f"Processed: {data}"
        >>>
        >>> if __name__ == "__main__":
        ...     mcp_server.run()
    """

    def __init__(self, config: ServerConfig):
        """Initialise MCP server with configuration.

        Args:
            config: Server configuration
        """
        self.config = config

        # Shared HTTP client for URLFetcher and other abstractions
        self.http_client: httpx.AsyncClient | None = None

        # Create FastMCP server with lifespan
        self.mcp = FastMCP(config.server_name, mask_error_details=config.mask_error_details, lifespan=self._create_lifespan_handler())

        # Configure middleware stack
        self._configure_middleware()

        logger.info(f"MCP server initialised: {config.server_name} (transport={config.transport}, env={config.environment})")

    def _configure_middleware(self) -> None:
        """Configure middleware stack in correct order.

        Middleware order matters:
        1. Error handling (catch all errors)
        2. Retry (retry transient failures)
        3. Rate limiting (before expensive operations)
        4. Timing (measure actual execution)
        5. Logging (log everything)
        """

        # 1. Error handling (include traceback in dev only)
        self.mcp.add_middleware(ErrorHandlingMiddleware(include_traceback=self.config.include_traceback, transform_errors=True))
        logger.debug("Added ErrorHandlingMiddleware")

        # 2. Retry middleware (if enabled)
        if self.config.retry_enabled:
            self.mcp.add_middleware(RetryMiddleware(max_retries=self.config.retry_max_attempts, retry_exceptions=(ConnectionError, TimeoutError)))
            logger.debug(f"Added RetryMiddleware (max_retries={self.config.retry_max_attempts})")

        # 3. Rate limiting (if enabled)
        if self.config.rate_limit_enabled:
            self.mcp.add_middleware(
                RateLimitingMiddleware(
                    max_requests_per_second=self.config.rate_limit_requests_per_second, burst_capacity=self.config.rate_limit_burst_capacity
                )
            )
            logger.debug(
                f"Added RateLimitingMiddleware (rps={self.config.rate_limit_requests_per_second}, burst={self.config.rate_limit_burst_capacity})"
            )

        # 4. Detailed timing
        self.mcp.add_middleware(DetailedTimingMiddleware())
        logger.debug("Added DetailedTimingMiddleware")

        # 5. Structured logging (transport-aware)
        logging_middleware = configure_logging(self.config)
        self.mcp.add_middleware(logging_middleware)
        logger.debug(f"Added StructuredLoggingMiddleware (transport={self.config.transport}, log_file={self.config.get_log_file_path()})")

    def _create_lifespan_handler(self):
        """Create lifespan handler for resource management.

        The lifespan handler manages the HTTP client lifecycle and makes it
        available to tools via the app_context dictionary.

        Returns:
            Callable that FastMCP uses as a lifespan context manager
        """

        @asynccontextmanager
        async def lifespan_handler(mcp: FastMCP):
            """Initialise resources on startup, cleanup on shutdown."""
            # Startup
            self.http_client = httpx.AsyncClient(timeout=self.config.url_timeout_seconds, follow_redirects=True)
            logger.debug("HTTP client initialised via lifespan")

            # Yield app_context dict that tools can access via ctx.app_context
            yield {"http_client": self.http_client, "config": self.config}

            # Shutdown
            if self.http_client:
                await self.http_client.aclose()
                logger.debug("HTTP client closed via lifespan")

        return lifespan_handler

    def get_http_client(self) -> httpx.AsyncClient:
        """Get the HTTP client instance.

        The HTTP client is available only after server startup (when run() is called).

        Returns:
            Shared httpx.AsyncClient instance

        Raises:
            RuntimeError: If called before server startup

        Example:
            >>> mcp_server = MCPServer(config)
            >>> # Server must be running for client to be available
            >>> # Tools access via ctx.app_context["http_client"] instead
        """
        if self.http_client is None:
            raise RuntimeError("Server not started. HTTP client available only during server runtime via ctx.app_context['http_client'].")
        return self.http_client

    def run(self) -> None:
        """Run the MCP server.

        Automatically selects transport based on configuration.
        """
        if self.config.transport == "stdio":
            logger.info("Starting server in STDIO mode")
            self.mcp.run(transport="stdio")
        elif self.config.transport == "http":
            logger.info(f"Starting server in HTTP mode with streaming (host={self.config.http_host}, port={self.config.http_port})")
            self.mcp.run(transport="http", host=self.config.http_host, port=self.config.http_port)
