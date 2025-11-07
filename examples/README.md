# MCP Server Core Constructs

A reusable fundation for building secure, production-ready MCP servers using FastMCP.

## What's Here

### `mcp_server_core/` - Reusable Platform Package

A minimal, security-focused foundation for building MCP servers.

**Features:**
- Transport-aware logging (STDIO file-based, HTTP stdout)
- Type-safe configuration (Pydantic Settings)
- Security abstractions (SSRF prevention, path traversal protection)
- Pre-configured middleware stack (using FastMCP built-ins)
- Minimal dependencies (FastMCP + pydantic-settings)

**[Read mcp_server_core documentation →](./mcp_server_core/README.md)**

### `example_server/` - Reference Implementation

A complete working server demonstrating how to use `mcp_server_core`.

**Demonstrates:**
- Web tools with SSRF prevention
- File tools with path traversal protection
- AI Precision Anti-Pattern avoidance
- Transport-aware logging
- FastMCP built-in middleware usage

**[Read example_server documentation →](./example_server/README.md)**

## Quick Start

### Prerequisites

Install `uv` (fast Python package installer):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup and Run

```bash
# From mcp_server_core directory
cd examples/mcp_server_core
make setup        # Create shared .venv (one-time)
make install-dev  # Install with dev dependencies
make test-cov     # Verify installation

# Run example server
cd ../example_server
make install-dev  # Install example server
make run          # Run in STDIO mode
```

That's it! The Makefile handles all setup, configuration, and dependency management.

### Manual Setup (Alternative)

If you prefer manual setup without Make:

```bash
cd examples
uv venv
source .venv/bin/activate
uv pip install -e ./mcp_server_core
uv pip install -e ./example_server

# Run server
cd example_server
cp .env.example .env  # Configure if needed
python server.py
```

## Architecture Overview

```
┌─────────────────────────────────────┐
│  example_server                     │
│  - Business logic tools             │
│  - Uses platform abstractions       │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  mcp_server_core Package            │
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
│  - Transport layer                  │
└─────────────────────────────────────┘
```

## Key Design Decisions

### 1. Leverage FastMCP Built-ins

FastMCP provides production-ready implementations of all core middleware:
- `LoggingMiddleware` / `StructuredLoggingMiddleware`
- `ErrorHandlingMiddleware` / `RetryMiddleware`
- `TimingMiddleware` / `DetailedTimingMiddleware`
- `RateLimitingMiddleware` / `SlidingWindowRateLimitingMiddleware`

**We use these directly - no custom implementations.**

See [fastmcp-builtin-features.md](../fastmcp-builtin-features.md) for details.

### 2. Security-First Abstractions

Instead of opinionated business logic abstractions (databases, APIs), we provide security boundary abstractions:

- **URLFetcher:** Prevents SSRF attacks, enforces HTTPS, size limits
- **FileOperations:** Prevents path traversal, enforces directory whitelist, safe permissions

These prevent common vulnerabilities while remaining flexible for different use cases.

### 3. Transport-Aware Logging

**CRITICAL:** STDIO mode uses stdout/stderr for the MCP protocol itself.

- **STDIO mode:** Logs to file (e.g., `/tmp/mcp-server.log`)
- **HTTP mode:** Logs to stdout (captured by container runtime)

This is handled automatically by `mcp_server_core`.

### 4. Minimal Dependencies

**Core dependencies:**
- `fastmcp>=2.9.0` (includes httpx, pydantic)
- `pydantic-settings>=2.0`

**Optional dependencies:**
- `opentelemetry-api` (distributed tracing)
- `prometheus-client` (metrics)
- `llm-sandbox` (sandboxed code execution)

## Research Foundation

These examples implement the patterns and recommendations from the comprehensive FastMCP architecture research:

- [Executive Summary](../fastmcp-executive-summary.md)
- [Technical Architecture](../fastmcp-technical-architecture.md)
- [Patterns & Anti-Patterns](../fastmcp-patterns-anti-patterns.md)
- [FastMCP Built-in Features](../fastmcp-builtin-features.md)

## Security Features

### SSRF Prevention (URLFetcher)

```python
from mcp_server_core.abstractions import URLFetcher

url_fetcher = URLFetcher(http_client, config)

# ✅ Safe: Public IP
await url_fetcher.fetch("https://api.github.com")

# ❌ Blocked: Private IP ranges
await url_fetcher.fetch("http://192.168.1.1")  # SecurityError
await url_fetcher.fetch("http://10.0.0.1")     # SecurityError
await url_fetcher.fetch("http://127.0.0.1")    # SecurityError
```

### Path Traversal Protection (FileOperations)

```python
from mcp_server_core.abstractions import FileOperations

file_ops = FileOperations(config)

# ✅ Safe: Within allowed directory
await file_ops.read_file("/tmp/data.txt")

# ❌ Blocked: Path traversal
await file_ops.read_file("/tmp/../etc/passwd")  # SecurityError

# ❌ Blocked: Outside allowed directories
await file_ops.read_file("/etc/passwd")  # SecurityError
```

### AI Precision Anti-Pattern Avoidance

```python
# ❌ WRONG: LLM doing calculations
@mcp.tool
async def calculate(expr: str, ctx: Context) -> float:
    prompt = f"Calculate: {expr}"
    return await llm.complete(prompt)  # Unreliable!

# ✅ CORRECT: Deterministic tool
@mcp.tool
def calculate_total(items: list[dict]) -> dict:
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    return {"subtotal": subtotal, "tax": subtotal * 0.10}
```

## Testing

Both packages include tests using FastMCP's in-memory transport:

```python
from fastmcp.client import Client

async def test_tool():
    async with Client(platform.mcp) as client:
        result = await client.call_tool("my_tool", {"param": "value"})
        assert result.data == "expected"
```

**Benefits:**
- Millisecond test execution (no network I/O)
- No mocking needed
- Identical to production behaviour

## Deployment Patterns

### Local Development (STDIO)

```bash
MCP_TRANSPORT=stdio python server.py
```

- Logs to file: `/tmp/mcp-server.log`
- For use with Claude Desktop
- Fast development iteration

### Cloud Production (HTTP)

```bash
MCP_TRANSPORT=http python server.py
```

- Logs to stdout → Container runtime → CloudWatch/Datadog
- For Kubernetes, ECS, Cloud Run, etc.
- Production-ready observability

## Best Practices

### 1. NEVER Log to stdout/stderr in STDIO Mode

```python
# ❌ WRONG
print("Debug info")           # Breaks STDIO protocol!
sys.stdout.write("Info")      # Breaks STDIO protocol!
logging.StreamHandler()       # Breaks STDIO protocol!

# ✅ CORRECT
await ctx.info("Debug info")  # Transport-aware
```

### 2. Use Security Abstractions

```python
# ❌ WRONG
import requests
response = requests.get(user_url)  # SSRF vulnerable!

# ✅ CORRECT
url_fetcher = URLFetcher(client, config)
response = await url_fetcher.fetch(user_url)  # SSRF protected
```

### 3. Use FastMCP Built-ins

```python
# ❌ WRONG
class MyLoggingMiddleware(Middleware):  # Already exists!
    ...

# ✅ CORRECT
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
mcp.add_middleware(StructuredLoggingMiddleware())
```

### 4. Deterministic Tools

```python
# LLMs orchestrate → Tools execute
# Never ask LLM to do maths, validation, or data transformation
```

## Next Steps

1. **Read the Documentation:**
   - [mcp_server_core README](./mcp_server_core/README.md)
   - [example_server README](./example_server/README.md)
   - [FastMCP Built-in Features](../fastmcp-builtin-features.md)

2. **Run the Example:**
   ```bash
   cd example_server
   cp .env.example .env
   python server.py
   ```

3. **Build Your Server:**
   - Copy `example_server` as a starting point
   - Add your domain-specific tools
   - Use `mcp_server_core` abstractions for security
   - Leverage FastMCP built-in middleware

## References

- [FastMCP Documentation](https://gofastmcp.com)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io)
- [Research Documentation](../README.md)

## License

MIT

## Makefile Usage

Both packages include modern Makefiles for streamlined development workflows.

### Quick Reference

```bash
# Setup (one-time)
make setup        # Create shared virtual environment
make install-dev  # Install with dev dependencies

# Development
make format       # Format code
make lint         # Check code style
make test-cov     # Run tests with coverage

# Package (mcp_server_core only)
make package      # Build distribution

# Server (example_server only)
make run          # Run example server
```
