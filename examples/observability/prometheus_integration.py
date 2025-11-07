"""Prometheus integration example for MCP servers.

This example demonstrates how to export Prometheus metrics from an MCP server
using custom middleware and the prometheus_client library.

Metrics exported:
- mcp_tool_calls_total: Total tool calls (counter)
- mcp_tool_duration_seconds: Tool execution duration (histogram)
- mcp_tool_errors_total: Total tool errors (counter)

Requirements:
    pip install prometheus-client

Usage:
    # Run server
    python prometheus_integration.py

    # Metrics available at http://localhost:9090/metrics

Configuration:
    Set via environment variables:
    - MCP_SERVER_NAME: Server name (required)
    - MCP_ENABLE_METRICS: Enable Prometheus metrics (default: false)
    - MCP_PROMETHEUS_PORT: Metrics endpoint port (default: 9090)
"""

import time

from fastmcp.server.middleware import Middleware, MiddlewareContext
from prometheus_client import Counter, Histogram, start_http_server

from mcp_server_core import MCPServer, ServerConfig

# Prometheus metrics
tool_calls = Counter("mcp_tool_calls_total", "Total tool calls", ["tool_name", "status"])

tool_duration = Histogram("mcp_tool_duration_seconds", "Tool execution duration", ["tool_name"])

tool_errors = Counter("mcp_tool_errors_total", "Total tool errors", ["tool_name", "error_type"])


class PrometheusMiddleware(Middleware):
    """Middleware to export Prometheus metrics.

    Tracks:
    - Tool call count (success/error)
    - Tool execution duration
    - Error types

    Example:
        >>> from mcp_server_core import MCPServer, ServerConfig
        >>> from prometheus_integration import PrometheusMiddleware
        >>>
        >>> mcp_server = MCPServer(ServerConfig())
        >>> mcp_server.mcp.add_middleware(PrometheusMiddleware())
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Track tool execution metrics."""
        tool_name = context.message.name
        start_time = time.time()

        try:
            result = await call_next(context)

            # Record success
            tool_calls.labels(tool_name=tool_name, status="success").inc()

            return result

        except Exception as e:
            # Record error
            tool_calls.labels(tool_name=tool_name, status="error").inc()
            tool_errors.labels(tool_name=tool_name, error_type=type(e).__name__).inc()

            raise

        finally:
            # Record duration
            duration = time.time() - start_time
            tool_duration.labels(tool_name=tool_name).observe(duration)


def configure_prometheus(config: ServerConfig):
    """Configure and start Prometheus metrics server.

    Args:
        config: Server configuration with metrics settings

    Example:
        >>> config = ServerConfig(
        ...     enable_metrics=True,
        ...     prometheus_port=9090
        ... )
        >>> configure_prometheus(config)
    """
    if not config.enable_metrics:
        return

    port = config.prometheus_port or 9090

    # Start metrics HTTP server
    start_http_server(port)
    print(f"Prometheus metrics endpoint started: http://localhost:{port}/metrics")


def main():
    """Example MCP server with Prometheus metrics."""
    # Load configuration
    config = ServerConfig()

    # Configure Prometheus metrics endpoint
    configure_prometheus(config)

    # Create MCP server
    mcp_server = MCPServer(config)

    # Add Prometheus middleware
    mcp_server.mcp.add_middleware(PrometheusMiddleware())

    @mcp_server.mcp.tool
    def example_tool(data: str) -> str:
        """Example tool that will be metered."""
        # Metrics automatically recorded
        return f"Processed: {data}"

    @mcp_server.mcp.tool
    def failing_tool() -> str:
        """Example tool that fails (for error metrics)."""
        raise ValueError("Example error")

    @mcp_server.mcp.tool
    def slow_tool(delay: int = 1) -> str:
        """Example slow tool (for duration metrics)."""
        import time

        time.sleep(delay)
        return f"Completed after {delay}s"

    # Run server
    print(f"Starting {config.server_name} with Prometheus metrics")
    print("Try these commands to test metrics:")
    print("  - Call example_tool to increment success counter")
    print("  - Call failing_tool to increment error counter")
    print("  - Call slow_tool to see duration histogram")
    print(f"\nMetrics: http://localhost:{config.prometheus_port or 9090}/metrics")

    mcp_server.run()


if __name__ == "__main__":
    main()
