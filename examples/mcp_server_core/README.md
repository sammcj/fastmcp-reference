# MCP Server Core

Reusable foundational components for building production-ready MCP servers.

## Overview

`mcp-server-core` provides a minimal, security-focused foundation for building MCP servers that run in production. It wraps FastMCP's excellent built-in features with production-ready patterns and security abstractions.

**Key Principles:**
- Leverage FastMCP built-ins (don't reinvent logging, error handling, middleware)
- Security-first abstractions (prevent SSRF, path traversal, etc.)
- Transport-aware logging (STDIO file-based, HTTP stdout)
- Minimal dependencies (FastMCP + pydantic-settings)
- Production-ready patterns

## Features

### ✅ What's Included

**Configuration Management**
- Type-safe config via Pydantic Settings
- Environment variable driven (12-factor app pattern)
- Validation with helpful error messages

**Transport-Aware Logging**
- STDIO mode: Logs to file (stdout/stderr reserved for MCP protocol)
- HTTP mode: Logs to stdout (captured by container runtime)
- Uses FastMCP's built-in StructuredLoggingMiddleware (JSON output)

**Security Abstractions**
- `URLFetcher`: SSRF prevention, HTTPS enforcement, size limits
- `FileOperations`: Path traversal protection, safe permissions (0600), directory whitelist

**Middleware Stack (FastMCP Built-ins)**
- `ErrorHandlingMiddleware`: Comprehensive error logging
- `RetryMiddleware`: Automatic retry with exponential backoff
- `RateLimitingMiddleware`: Token bucket rate limiting
- `DetailedTimingMiddleware`: Performance monitoring

### ❌ What's NOT Included (Use FastMCP Directly)

- Custom logging libraries (FastMCP's is excellent)
- Custom error handling (FastMCP provides `ErrorHandlingMiddleware`)
- Custom middleware framework (FastMCP has a complete system)
- Database abstractions (too opinionated, implement at application level)

## Installation

### Prerequisites

Install `uv` (fast Python package installer):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

```bash
# From mcp_server_core directory
cd examples/mcp_server_core

# Create shared virtual environment (one-time)
make setup

# Install with development dependencies
make install-dev

# Verify installation
make test-cov
```

### Manual Installation (Alternative)

If you prefer manual setup:

```bash
# Core dependencies only
pip install fastmcp pydantic-settings

# Or install from local directory
pip install -e /path/to/mcp-server-core
```

## Quick Start

### 1. Create Configuration

```python
# .env file
MCP_SERVER_NAME=my-server
MCP_TRANSPORT=stdio
MCP_LOG_LEVEL=INFO
MCP_ENVIRONMENT=production
```

### 2. Create Server

```python
from mcp_server_core import ServerConfig, MCPServer
from fastmcp import Context

# Load configuration
config = ServerConfig()

# Create MCP server (automatically configures middleware)
mcp_server = MCPServer(config)

# Register tools
@mcp_server.mcp.tool
def my_tool(data: str, ctx: Context) -> str:
    return f"Processed: {data}"

# Run server
if __name__ == "__main__":
    mcp_server.run()
```

### 3. Use Security Abstractions

```python
from mcp_server_core.abstractions import URLFetcher, FileOperations

async with mcp_server:
    # URL fetching with SSRF prevention
    url_fetcher = URLFetcher(mcp_server.http_client, config)
    response = await url_fetcher.fetch("https://api.example.com")

    # File operations with path traversal protection
    file_ops = FileOperations(config)
    content = await file_ops.read_file("/tmp/data.txt")
```

## Configuration Reference

All configuration via environment variables with `MCP_` prefix:

### Server Identity
- `MCP_SERVER_NAME` (required): Server name
- `MCP_ENVIRONMENT`: `dev`, `staging`, `production` (default: `production`)

### Transport & Logging
- `MCP_TRANSPORT`: `stdio`, `http` (default: `stdio`)
- `MCP_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `MCP_LOG_FILE`: Log file path for STDIO mode (default: `/tmp/mcp-{server_name}.log`)
- `MCP_LOG_INCLUDE_PAYLOADS`: Include request/response payloads (default: `false`)

### Error Handling
- `MCP_MASK_ERROR_DETAILS`: Mask internal errors (default: `true`)
- `MCP_INCLUDE_TRACEBACK`: Include stack traces (default: `false`)

### Rate Limiting
- `MCP_RATE_LIMIT_ENABLED`: Enable rate limiting (default: `true`)
- `MCP_RATE_LIMIT_REQUESTS_PER_SECOND`: Requests/second (default: `10.0`)
- `MCP_RATE_LIMIT_BURST_CAPACITY`: Burst capacity (default: `20`)

### File Operations Security
- `MCP_ALLOWED_FILE_DIRECTORIES`: JSON list of allowed directories (default: `["/tmp", "./data"]`)
- `MCP_MAX_FILE_SIZE_MB`: Max file size (default: `100`)
- `MCP_FILE_DEFAULT_PERMISSIONS`: File permissions in octal (default: `0600` = owner read/write only)

### URL Fetching Security
- `MCP_URL_ALLOW_PRIVATE_IPS`: Allow private IPs (default: `false`)
- `MCP_URL_REQUIRE_HTTPS`: Require HTTPS (default: `true`)
- `MCP_URL_MAX_SIZE_MB`: Max response size (default: `10`)
- `MCP_URL_TIMEOUT_SECONDS`: Request timeout (default: `30`)

## Security Abstractions

### URLFetcher

Prevents SSRF attacks by blocking private IP ranges:

```python
from mcp_server_core.abstractions import URLFetcher
from mcp_server_core.exceptions import SecurityError

url_fetcher = URLFetcher(http_client, config)

# Safe: Public IP
response = await url_fetcher.fetch("https://api.github.com")

# Blocked: Private IP (raises SecurityError)
try:
    await url_fetcher.fetch("http://192.168.1.1")  # SSRF protection
except SecurityError as e:
    print(f"Blocked: {e}")

# Blocked: HTTP in production (raises SecurityError)
try:
    await url_fetcher.fetch("http://example.com")  # HTTPS required
except SecurityError as e:
    print(f"Blocked: {e}")
```

### FileOperations

Prevents path traversal and enforces directory whitelist:

```python
from mcp_server_core.abstractions import FileOperations
from mcp_server_core.exceptions import SecurityError

file_ops = FileOperations(config)

# Safe: Within allowed directory
content = await file_ops.read_file("/tmp/data.txt")

# Blocked: Path traversal (raises SecurityError)
try:
    await file_ops.read_file("/tmp/../etc/passwd")
except SecurityError as e:
    print(f"Blocked: {e}")

# Blocked: Outside allowed directories (raises SecurityError)
try:
    await file_ops.read_file("/etc/passwd")
except SecurityError as e:
    print(f"Blocked: {e}")

# Write with safe permissions (0600 by default)
await file_ops.write_file("/tmp/output.txt", b"Hello, World!")
# File created with owner read/write only (0600)
```

## Architecture

```
┌─────────────────────────────────────┐
│  Your Server (Example Server)      │
│  - Tools using abstractions         │
│  - Business logic                   │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  mcp_server_core Package               │
│  - Configuration (Pydantic)         │
│  - Transport-aware logging          │
│  - Security abstractions            │
│  - Middleware configuration         │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  FastMCP Framework                  │
│  - MCP protocol handler             │
│  - Built-in middleware              │
│  - Transport layer (STDIO/HTTP)     │
└─────────────────────────────────────┘
```

## Best Practices

### 1. NEVER Log to stdout/stderr in STDIO Mode

```python
# ❌ WRONG - Breaks MCP STDIO protocol
print("Processing request")
sys.stdout.write("Debug info")

# ✅ CORRECT - Use Context logging
@mcp_server.mcp.tool
async def my_tool(data: str, ctx: Context) -> str:
    await ctx.info("Processing request")
    return f"Processed: {data}"
```

### 2. Use Security Abstractions

```python
# ❌ WRONG - Vulnerable to SSRF
import requests
response = requests.get(user_provided_url)  # No validation!

# ✅ CORRECT - SSRF prevention built-in
url_fetcher = URLFetcher(http_client, config)
response = await url_fetcher.fetch(user_provided_url)
```

### 3. Use FastMCP Built-in Middleware

```python
# ❌ WRONG - Don't reinvent middleware
class MyLoggingMiddleware(Middleware):  # FastMCP already has this!
    async def on_message(self, context, call_next):
        # ... custom logging logic

# ✅ CORRECT - Use FastMCP's built-ins
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
mcp.add_middleware(StructuredLoggingMiddleware())
```

### 4. Deterministic Tools (AI Precision Anti-Pattern)

```python
# ❌ WRONG - LLM doing calculations
@mcp_server.mcp.tool
async def calculate_total(items: list, ctx: Context) -> float:
    # Ask LLM to calculate total (unreliable!)
    prompt = f"Calculate total for: {items}"
    return await llm.complete(prompt)

# ✅ CORRECT - Deterministic tool
@mcp_server.mcp.tool
def calculate_total(items: list[dict]) -> dict:
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    tax = subtotal * 0.10
    return {"subtotal": subtotal, "tax": tax, "total": subtotal + tax}
```

## Testing

### Running Tests

```bash
# Run tests with coverage report
make test-cov

# Run tests without coverage
make test

# Format and lint code
make format
make lint
```

See [MAKEFILE_GUIDE.md](../MAKEFILE_GUIDE.md) for all available targets.

### Writing Tests

Use FastMCP's in-memory transport for fast tests:

```python
import pytest
from fastmcp.client import Client
from mcp_server_core import ServerConfig, MCPServer

@pytest.fixture
async def test_client():
    config = ServerConfig(server_name="test-server", environment="dev")
    mcp_server = MCPServer(config)

    @mcp_server.mcp.tool
    def add(a: int, b: int) -> int:
        return a + b

    async with Client(mcp_server.mcp) as client:
        yield client

async def test_add_tool(test_client):
    result = await test_client.call_tool("add", {"a": 5, "b": 3})
    assert result.data == 8
```

## Dependencies

**Core (2 packages):**
- `fastmcp>=2.12.3` - MCP framework (includes httpx, pydantic)
- `pydantic-settings>=2.11` - Configuration management

**Optional:**
- `opentelemetry-api` - Distributed tracing
- `prometheus-client` - Metrics export
- `llm-sandbox` - Sandboxed code execution

## License

MIT

## References

- [FastMCP Documentation](https://gofastmcp.com)
- [FastMCP Built-in Features Guide](../research/fastmcp-builtin-features.md)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io)
