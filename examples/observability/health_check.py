"""Health check endpoint implementation for MCP servers.

Provides HTTP endpoints for health and readiness checks,
suitable for Kubernetes, ALB, and other orchestration systems.

Endpoints:
    GET /health  - Liveness check (is server running?)
    GET /ready   - Readiness check (is server ready to accept requests?)

Requirements:
    pip install fastapi uvicorn

Usage:
    # Run server with health checks
    python health_check.py

    # Check health
    curl http://localhost:8001/health

    # Check readiness
    curl http://localhost:8001/ready

Configuration:
    Set via environment variables:
    - MCP_HEALTH_CHECK_ENABLED: Enable health checks (default: false)
    - MCP_HEALTH_CHECK_PORT: Health check port (default: 8001)
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Response
from mcp_server_core import MCPServer, ServerConfig

# Create FastAPI app for health checks
health_app = FastAPI(title="MCP Health Checks")


class HealthChecker:
    """Health and readiness checker for MCP server.

    Checks:
    - Health: Is the server process running?
    - Readiness: Are all dependencies available?
        - HTTP client initialized
        - File system accessible
        - Configuration valid

    Example:
        >>> from mcp_server_core import MCPServer, ServerConfig
        >>> from health_check import HealthChecker
        >>>
        >>> config = ServerConfig()
        >>> mcp_server = MCPServer(config)
        >>> checker = HealthChecker(mcp_server, config)
        >>>
        >>> # Start health check server
        >>> await checker.start()
    """

    def __init__(self, mcp_server: MCPServer, config: ServerConfig):
        """Initialise health checker.

        Args:
            mcp_server: MCP server instance to check
            config: Server configuration
        """
        self.mcp_server = mcp_server
        self.config = config
        self.health_server_task = None

    @health_app.get("/health")
    async def health_check(self):
        """Liveness check - is server running?

        Returns:
            200 OK: Server is alive
        """
        return {
            "status": "healthy",
            "server": self.config.server_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @health_app.get("/ready")
    async def readiness_check(self):
        """Readiness check - is server ready to accept requests?

        Checks:
        - HTTP client initialized
        - File system accessible
        - All required services available

        Returns:
            200 OK: Server is ready
            503 Service Unavailable: Server not ready
        """
        checks = {}

        # Check HTTP client
        if self.mcp_server.http_client:
            checks["http_client"] = "ready"
        else:
            checks["http_client"] = "not_ready"

        # Check file system
        try:
            Path("/tmp").exists()
            checks["filesystem"] = "ready"
        except Exception:
            checks["filesystem"] = "not_ready"

        # Check configuration
        try:
            assert self.config.server_name
            checks["configuration"] = "ready"
        except Exception:
            checks["configuration"] = "not_ready"

        # Determine overall readiness
        all_ready = all(v == "ready" for v in checks.values())
        status_code = 200 if all_ready else 503

        return Response(
            content={
                "status": "ready" if all_ready else "not_ready",
                "checks": checks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status_code=status_code,
        )

    async def start(self):
        """Start health check HTTP server.

        Runs in background task alongside MCP server.
        """
        if not self.config.health_check_enabled:
            return

        import uvicorn

        port = self.config.health_check_port or 8001

        # Create uvicorn config
        uv_config = uvicorn.Config(health_app, host="0.0.0.0", port=port, log_level="error")

        # Create server
        server = uvicorn.Server(uv_config)

        # Run in background
        self.health_server_task = asyncio.create_task(server.serve())

        print(f"Health check endpoints:")
        print(f"  - Liveness:  http://localhost:{port}/health")
        print(f"  - Readiness: http://localhost:{port}/ready")


async def run_with_health_checks():
    """Run MCP server with health check endpoints."""
    # Load configuration
    config = ServerConfig()

    # Create MCP server
    mcp_server = MCPServer(config)

    @mcp_server.mcp.tool
    def example_tool(data: str) -> str:
        """Example tool."""
        return f"Processed: {data}"

    # Create health checker
    checker = HealthChecker(mcp_server, config)

    # Start health check server
    await checker.start()

    # Initialize MCP server resources
    async with mcp_server:
        # Server is now ready
        print(f"MCP server ready: {config.server_name}")

        # Keep running
        while True:
            await asyncio.sleep(1)


def main():
    """Example MCP server with health checks."""
    print("Starting MCP server with health checks...")
    asyncio.run(run_with_health_checks())


if __name__ == "__main__":
    main()
