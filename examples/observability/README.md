# Observability Integration Examples

This directory contains working examples of integrating observability tools with MCP servers built using the `mcp-server-core` package.

## Examples

### 1. OpenTelemetry Integration (`otel_integration.py`)

Demonstrates distributed tracing with OpenTelemetry.

**Features:**
- OTLP gRPC exporter
- Automatic span creation for tool calls
- Service name configuration
- Batch span processing

**Requirements:**
```bash
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-otlp-proto-grpc
```

**Configuration:**
```bash
export MCP_ENABLE_TRACING=true
export MCP_OTLP_ENDPOINT="http://localhost:4317"
export MCP_OTEL_SERVICE_NAME="my-mcp-server"
```

**Usage:**
```bash
python otel_integration.py
```

**Viewing Traces:**
- Use Jaeger, Zipkin, or other OTLP-compatible backend
- Default OTLP endpoint: `http://localhost:4317`

---

### 2. Prometheus Integration (`prometheus_integration.py`)

Demonstrates metrics export with Prometheus.

**Metrics:**
- `mcp_tool_calls_total`: Total tool calls (counter)
- `mcp_tool_duration_seconds`: Tool execution duration (histogram)
- `mcp_tool_errors_total`: Total tool errors (counter)

**Requirements:**
```bash
pip install prometheus-client
```

**Configuration:**
```bash
export MCP_ENABLE_METRICS=true
export MCP_PROMETHEUS_PORT=9090
```

**Usage:**
```bash
python prometheus_integration.py

# View metrics
curl http://localhost:9090/metrics
```

**Prometheus Configuration:**
```yaml
scrape_configs:
  - job_name: 'mcp-server'
    static_configs:
      - targets: ['localhost:9090']
```

---

### 3. Health Check Endpoint (`health_check.py`)

Demonstrates liveness and readiness checks for orchestration systems.

**Endpoints:**
- `GET /health`: Liveness probe (is server running?)
- `GET /ready`: Readiness probe (is server ready?)

**Requirements:**
```bash
pip install fastapi uvicorn
```

**Configuration:**
```bash
export MCP_HEALTH_CHECK_ENABLED=true
export MCP_HEALTH_CHECK_PORT=8001
```

**Usage:**
```bash
python health_check.py

# Check health
curl http://localhost:8001/health

# Check readiness
curl http://localhost:8001/ready
```

**Kubernetes Integration:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8001
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## Configuration Reference

All examples use environment variables from `mcp-server-core.ServerConfig`:

### OpenTelemetry
- `MCP_ENABLE_TRACING`: Enable tracing (default: `false`)
- `MCP_OTLP_ENDPOINT`: OTLP gRPC endpoint (required if tracing enabled)
- `MCP_OTEL_SERVICE_NAME`: Service name for traces (default: `server_name`)

### Prometheus
- `MCP_ENABLE_METRICS`: Enable metrics (default: `false`)
- `MCP_PROMETHEUS_PORT`: Metrics HTTP port (default: `9090`)

### Health Checks
- `MCP_HEALTH_CHECK_ENABLED`: Enable health checks (default: `false`)
- `MCP_HEALTH_CHECK_PORT`: Health check HTTP port (default: `8001`)

---

## Combined Example

Run all observability features together:

```python
from mcp_server_core import MCPServer, ServerConfig
from otel_integration import configure_tracing
from prometheus_integration import PrometheusMiddleware, configure_prometheus
from health_check import HealthChecker

async def main():
    config = ServerConfig(
        enable_tracing=True,
        otlp_endpoint="http://localhost:4317",
        enable_metrics=True,
        prometheus_port=9090,
        health_check_enabled=True,
        health_check_port=8001
    )

    # Configure OpenTelemetry
    configure_tracing(config)

    # Configure Prometheus
    configure_prometheus(config)

    # Create MCP server
    mcp_server = MCPServer(config)

    # Add Prometheus middleware
    mcp_server.mcp.add_middleware(PrometheusMiddleware())

    # Add tools
    @mcp_server.mcp.tool
    def example_tool(data: str) -> str:
        return f"Processed: {data}"

    # Start health checks
    checker = HealthChecker(mcp_server, config)
    await checker.start()

    # Run server
    async with mcp_server:
        mcp_server.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Notes

### Production Considerations

1. **OpenTelemetry**
   - Use batch span processing (default in examples)
   - Configure sampling for high-volume services
   - Set appropriate OTLP endpoint for production

2. **Prometheus**
   - Enable metrics scraping in production
   - Configure alerting rules
   - Use Prometheus Pushgateway for short-lived jobs

3. **Health Checks**
   - Set appropriate timeouts for readiness checks
   - Configure Kubernetes probes correctly
   - Monitor health check endpoint availability

### Security

- Health check endpoints expose server information
- Use network policies to restrict health check access
- Consider authentication for metrics endpoints in production

### Performance

- OpenTelemetry batching reduces overhead
- Prometheus scraping is pull-based (no server overhead)
- Health checks are lightweight HTTP endpoints

---

## Troubleshooting

### OpenTelemetry

**Issue:** Traces not appearing

**Solution:**
- Verify OTLP endpoint is reachable
- Check firewall rules
- Ensure OTLP collector is running
- Enable debug logging: `export OTEL_LOG_LEVEL=debug`

### Prometheus

**Issue:** Metrics endpoint not accessible

**Solution:**
- Verify port is not in use: `lsof -i :9090`
- Check firewall rules
- Ensure `MCP_ENABLE_METRICS=true`

### Health Checks

**Issue:** Readiness check failing

**Solution:**
- Check HTTP client initialization
- Verify file system access
- Review readiness check logs
- Test dependencies individually

---

**Last Updated:** 28 October 2025
