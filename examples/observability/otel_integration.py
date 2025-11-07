"""OpenTelemetry integration example for MCP servers.

This example demonstrates how to configure OpenTelemetry tracing
for an MCP server using FastMCP's built-in middleware.

Requirements:
    pip install opentelemetry-api opentelemetry-sdk
    pip install opentelemetry-exporter-otlp-proto-grpc

Usage:
    # Set OTLP endpoint
    export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"

    # Run server
    python otel_integration.py

Configuration:
    Set via environment variables:
    - MCP_SERVER_NAME: Server name (required)
    - MCP_ENABLE_TRACING: Enable tracing (default: false)
    - MCP_OTLP_ENDPOINT: OTLP endpoint (required if tracing enabled)
    - MCP_OTEL_SERVICE_NAME: Service name for traces (default: server_name)
"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from mcp_server_core import MCPServer, ServerConfig


def configure_tracing(config: ServerConfig):
    """Configure OpenTelemetry tracing.

    Args:
        config: Server configuration with tracing settings

    Example:
        >>> config = ServerConfig(
        ...     enable_tracing=True,
        ...     otlp_endpoint="http://localhost:4317"
        ... )
        >>> configure_tracing(config)
    """
    if not config.enable_tracing or not config.otlp_endpoint:
        return

    # Create resource with service name
    resource = Resource(attributes={SERVICE_NAME: config.otel_service_name or config.server_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter with batch processor
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otlp_endpoint, insecure=True))
    provider.add_span_processor(processor)

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    print(f"OpenTelemetry tracing configured: {config.otlp_endpoint}")


def main():
    """Example MCP server with OpenTelemetry tracing."""
    # Load configuration
    config = ServerConfig()

    # Configure tracing
    configure_tracing(config)

    # Create MCP server (with tracing automatically enabled if configured)
    mcp_server = MCPServer(config)

    @mcp_server.mcp.tool
    def example_tool(data: str) -> str:
        """Example tool that will be traced."""
        # Tool execution will be automatically traced via OpenTelemetry
        return f"Processed: {data}"

    @mcp_server.mcp.tool
    def another_tool(value: int) -> int:
        """Another example tool."""
        return value * 2

    # Run server
    print(f"Starting {config.server_name} with OpenTelemetry tracing")
    mcp_server.run()


if __name__ == "__main__":
    main()
