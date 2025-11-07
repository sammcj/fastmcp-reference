# CLAUDE.md - Example MCP Server

This file provides guidance to Claude Code when working with the example MCP server implementation.

---

## Server Purpose

This is a **reference implementation** demonstrating how to build production-ready MCP servers using the `mcp-server-core` package and FastMCP framework. It showcases best practices for security, tool design, and transport-aware logging.

**What This Server Demonstrates:**
- Using `mcp-server-core` for configuration and security
- FastMCP built-in middleware (logging, error handling, rate limiting, retry, timing)
- Security abstractions (SSRF prevention, path traversal protection)
- Transport-aware logging (STDIO file-based, HTTP stdout)
- AI Precision Anti-Pattern avoidance (deterministic calculations in tools)

**This is NOT production code** - it's a learning reference and starting point for building your own MCP servers.

---

## Server Structure

```
example_server/
├── server.py              # Main entry point - server setup
├── tools/
│   ├── __init__.py
│   ├── web_tools.py       # fetch_url, fetch_json (URLFetcher)
│   ├── file_tools.py      # read_file, write_file, list_directory (FileOperations)
│   └── example_tools.py   # calculate_total (AI Precision Anti-Pattern avoidance)
├── tests/
│   ├── test_web_tools.py
│   ├── test_file_tools.py
│   └── test_example_tools.py
├── .env.example           # Configuration template
├── pyproject.toml         # Dependencies and test configuration
└── README.md
```

---

## Critical FastMCP Concepts

### 1. Transport Modes

**STDIO (Local Development):**
- For use with Claude Desktop
- JSON-RPC over stdin/stdout
- **CRITICAL:** Cannot log to stdout/stderr (reserved for protocol)
- Logs go to file: `/tmp/mcp-example-server.log`

**HTTP with Streaming (Cloud Production):**
- For Kubernetes, ECS, Cloud Run, etc.
- RESTful HTTP with streaming support
- Logs go to stdout (captured by container runtime → CloudWatch/Datadog)

```bash
# STDIO mode
MCP_TRANSPORT=stdio python server.py

# HTTP mode
MCP_TRANSPORT=http python server.py
```

### 2. Context-Based Logging

**NEVER use print() or logging to stdout/stderr in STDIO mode:**

```python
# ❌ WRONG - Corrupts MCP protocol in STDIO mode
print("Processing request")
logging.info("Debug info")
sys.stdout.write("Data")

# ✅ CORRECT - Transport-aware logging
@mcp.tool
async def my_tool(data: str, ctx: Context) -> str:
    await ctx.info("Processing request")
    await ctx.debug(f"Received: {data}")
    return f"Processed: {data}"
```

### 3. Tool Design Principles

**Tools should be deterministic and focused:**

- **LLM role:** Orchestration (decide which tool to call)
- **Tool role:** Precise execution (maths, validation, data transformation)

```python
# ❌ WRONG - "Fat Tool" with multiple modes
@mcp.tool
async def file_operation(
    operation: str,  # "read" | "write" | "delete" | "list"
    path: str,
    content: str | None = None,
    recursive: bool = False,
    mode: str = "text",
    ctx: Context = None
) -> dict:
    # Too many parameters, confuses LLMs
    ...

# ✅ CORRECT - Focused tools
@mcp.tool
async def read_file(file_path: str, ctx: Context) -> str:
    """Read file content."""
    ...

@mcp.tool
async def write_file(file_path: str, content: str, ctx: Context) -> str:
    """Write content to file."""
    ...

@mcp.tool
async def list_directory(dir_path: str, ctx: Context) -> list[str]:
    """List files in directory."""
    ...
```

### 4. AI Precision Anti-Pattern

**NEVER ask LLMs to do deterministic tasks:**

```python
# ❌ WRONG - LLM doing calculations (unreliable!)
@mcp.tool
async def calculate_order_total(items: list, ctx: Context) -> str:
    prompt = f"Calculate total price for these items: {items}"
    return await llm.complete(prompt)  # Unreliable!

# ✅ CORRECT - Deterministic tool
@mcp.tool
def calculate_total(items: list[dict]) -> dict:
    """Calculate order total with tax.

    LLM decides to call this tool.
    Tool executes precise arithmetic.
    """
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    tax = round(subtotal * 0.10, 2)
    total = round(subtotal + tax, 2)

    return {
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "item_count": len(items)
    }
```

**Examples of deterministic tasks (tools should handle):**
- Mathematics and calculations
- Data format conversions (JSON ↔ CSV, etc.)
- Input validation
- Data aggregation and statistics
- Regular expressions and pattern matching

**Examples of non-deterministic tasks (LLMs should handle):**
- Natural language understanding
- Content summarisation
- Creative writing
- Ambiguity resolution
- User intent interpretation

---

## Security Features

### SSRF Prevention (URLFetcher)

The `web_tools.py` module uses `URLFetcher` to prevent Server-Side Request Forgery:

```python
from mcp_server_core.abstractions import URLFetcher

@mcp.tool
async def fetch_url(url: str, ctx: Context) -> str:
    """Fetch content from URL with SSRF protection."""
    url_fetcher = URLFetcher(ctx.app_context["http_client"], ctx.app_context["config"])

    try:
        content = await url_fetcher.fetch(url)
        return content
    except SecurityError as e:
        await ctx.error(f"Security error: {e}")
        raise
```

**What's blocked:**
- Private IP ranges (10.x.x.x, 192.168.x.x, 127.x.x.x)
- Local network addresses (169.254.x.x)
- HTTP requests in production (HTTPS required)
- Responses >10MB (configurable)

**Example:**
```python
# ✅ Safe
await fetch_url("https://api.github.com", ctx)

# ❌ Blocked - Private IP
await fetch_url("http://192.168.1.1", ctx)  # SecurityError

# ❌ Blocked - HTTP in production
await fetch_url("http://example.com", ctx)  # SecurityError if MCP_ENVIRONMENT=production
```

### Path Traversal Protection (FileOperations)

The `file_tools.py` module uses `FileOperations` to prevent path traversal attacks:

```python
from mcp_server_core.abstractions import FileOperations

@mcp.tool
async def read_file(file_path: str, ctx: Context) -> str:
    """Read file with path traversal protection."""
    file_ops = FileOperations(ctx.app_context["config"])

    try:
        content = await file_ops.read_file(file_path)
        return content.decode("utf-8")
    except SecurityError as e:
        await ctx.error(f"Security error: {e}")
        raise
```

**What's blocked:**
- Path traversal attempts (`../`, `..\\`)
- Access outside allowed directories (default: `/tmp`, `./data`)
- Files >100MB (configurable)

**What's enforced:**
- Files created with 0600 permissions (owner read/write only)
- Directory whitelist validation
- Canonical path resolution

**Example:**
```python
# ✅ Safe - Within allowed directory
await read_file("/tmp/data.txt", ctx)

# ❌ Blocked - Path traversal
await read_file("/tmp/../etc/passwd", ctx)  # SecurityError

# ❌ Blocked - Outside whitelist
await read_file("/etc/passwd", ctx)  # SecurityError

# ✅ Safe - Files created with 0600
await write_file("/tmp/secret.txt", "sensitive data", ctx)
```

---

## Middleware Stack

The server automatically configures FastMCP built-in middleware via `mcp-server-core`:

1. **ErrorHandlingMiddleware** - Catches and logs all errors
2. **RetryMiddleware** - Retries transient failures (3 attempts, exponential backoff)
3. **RateLimitingMiddleware** - Token bucket (10 req/s, burst 20)
4. **DetailedTimingMiddleware** - Performance monitoring
5. **StructuredLoggingMiddleware** - JSON logging (transport-aware)

**You don't need to implement any of these** - they're provided by FastMCP and configured by `mcp-server-core`.

---

## Configuration

All configuration via environment variables (`.env` file):

### Required
```bash
MCP_SERVER_NAME=example-server
```

### Transport Mode
```bash
# STDIO (local development, Claude Desktop)
MCP_TRANSPORT=stdio
MCP_LOG_FILE=/tmp/mcp-example-server.log

# HTTP (cloud deployment)
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8000
```

### Environment
```bash
# Development
MCP_ENVIRONMENT=dev
MCP_MASK_ERROR_DETAILS=false
MCP_INCLUDE_TRACEBACK=true
MCP_URL_ALLOW_PRIVATE_IPS=true   # For local testing
MCP_URL_REQUIRE_HTTPS=false      # For local testing

# Production
MCP_ENVIRONMENT=production
MCP_MASK_ERROR_DETAILS=true
MCP_INCLUDE_TRACEBACK=false
MCP_URL_ALLOW_PRIVATE_IPS=false  # SSRF protection
MCP_URL_REQUIRE_HTTPS=true       # Force HTTPS
```

### Security
```bash
# File operations
MCP_ALLOWED_FILE_DIRECTORIES=["/tmp", "./data"]
MCP_MAX_FILE_SIZE_MB=100
MCP_FILE_DEFAULT_PERMISSIONS=0600

# URL fetching
MCP_URL_MAX_SIZE_MB=10
MCP_URL_TIMEOUT_SECONDS=30

# Rate limiting
MCP_RATE_LIMIT_REQUESTS_PER_SECOND=10.0
MCP_RATE_LIMIT_BURST_CAPACITY=20
```

---

## Development Workflow

### Using the Makefile

```bash
# Setup (one-time)
cd ../mcp_server_core
make setup        # Create shared .venv at ../.venv

cd ../example_server

# Development
make install-dev  # Install with dev dependencies
make run          # Run server in STDIO mode
make test-cov     # Run tests with coverage
make format       # Format code with ruff
make lint         # Check code style
```

### Running the Server

```bash
# STDIO mode (for Claude Desktop)
make run
# or
python server.py

# HTTP mode (for cloud deployment)
MCP_TRANSPORT=http python server.py
```

### Testing

Tests use FastMCP's in-memory transport:

```python
import pytest
from fastmcp.client import Client

async def test_calculate_total(test_client):
    """Test calculate_total tool."""
    result = await test_client.call_tool("calculate_total", {
        "items": [
            {"name": "Widget", "price": 10.0, "quantity": 2},
            {"name": "Gadget", "price": 5.0, "quantity": 1}
        ]
    })

    assert result.data["subtotal"] == 25.0
    assert result.data["tax"] == 2.5
    assert result.data["total"] == 27.5
```

**Run tests:**
```bash
make test-cov  # With coverage report
make test      # Without coverage
```

---

## Critical Anti-Patterns to Avoid

### ⚠️ CRITICAL: STDIO Protocol Violation

```python
# ❌ WRONG
@mcp.tool
async def process_data(data: str, ctx: Context) -> str:
    print(f"Processing: {data}")  # Breaks STDIO protocol!
    return "done"

# ✅ CORRECT
@mcp.tool
async def process_data(data: str, ctx: Context) -> str:
    await ctx.info(f"Processing: {data}")  # Transport-aware
    return "done"
```

### ⚠️ CRITICAL: AI Precision Anti-Pattern

```python
# ❌ WRONG - LLM doing maths
@mcp.tool
async def calculate(expression: str, ctx: Context) -> str:
    prompt = f"Calculate: {expression}"
    return await llm.complete(prompt)  # Unreliable!

# ✅ CORRECT - Deterministic calculation
@mcp.tool
def calculate(a: float, b: float, operation: str) -> float:
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    # ... etc
```

### ⚠️ CRITICAL: Security Abstraction Bypass

```python
# ❌ WRONG - Bypasses SSRF protection
import requests

@mcp.tool
async def fetch(url: str, ctx: Context) -> str:
    response = requests.get(url)  # No validation!
    return response.text

# ✅ CORRECT - Uses security abstraction
@mcp.tool
async def fetch_url(url: str, ctx: Context) -> str:
    url_fetcher = URLFetcher(ctx.app_context["http_client"], ctx.app_context["config"])
    return await url_fetcher.fetch(url)
```

### ⚠️ HIGH: Fat Tools

```python
# ❌ WRONG - Too many parameters and modes
@mcp.tool
async def manage_files(
    operation: str,  # "read" | "write" | "delete" | "list" | "move" | "copy"
    source: str,
    destination: str | None = None,
    content: str | None = None,
    recursive: bool = False,
    force: bool = False,
    ctx: Context = None
) -> dict:
    # LLMs struggle with complex parameter combinations
    ...

# ✅ CORRECT - Focused tools
@mcp.tool
async def read_file(file_path: str, ctx: Context) -> str:
    """Read a single file."""
    ...

@mcp.tool
async def write_file(file_path: str, content: str, ctx: Context) -> str:
    """Write content to a single file."""
    ...
```

### ⚠️ HIGH: Sync I/O in Async Context

```python
# ❌ WRONG - Blocks event loop
@mcp.tool
async def fetch(url: str, ctx: Context) -> str:
    import requests
    response = requests.get(url)  # Blocks!
    return response.text

# ✅ CORRECT - Async HTTP client
@mcp.tool
async def fetch_url(url: str, ctx: Context) -> str:
    url_fetcher = URLFetcher(ctx.app_context["http_client"], ctx.app_context["config"])
    return await url_fetcher.fetch(url)  # Uses httpx (async)
```

---

## Adding New Tools

### 1. Create Tool Module

```python
# tools/my_tools.py
from fastmcp import Context
from mcp_server_core.abstractions import URLFetcher, FileOperations

def register_my_tools(mcp):
    """Register custom tools."""

    @mcp.tool
    async def my_tool(param: str, ctx: Context) -> str:
        """Tool description for LLM.

        Args:
            param: Parameter description
            ctx: FastMCP context

        Returns:
            Result description
        """
        await ctx.info(f"Processing: {param}")

        # Use security abstractions from context
        config = ctx.app_context["config"]
        http_client = ctx.app_context["http_client"]

        # Your logic here
        result = f"Processed: {param}"

        await ctx.debug(f"Result: {result}")
        return result
```

### 2. Register in server.py

```python
from tools.my_tools import register_my_tools

# ... server setup ...

register_my_tools(mcp_server.mcp)
```

### 3. Add Tests

```python
# tests/test_my_tools.py
import pytest
from fastmcp.client import Client

async def test_my_tool(test_client):
    result = await test_client.call_tool("my_tool", {"param": "test"})
    assert result.data == "Processed: test"
```

### 4. Update Documentation

Add tool documentation to README.md under "Available Tools" section.

---

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_web_tools.py     # URLFetcher usage tests
├── test_file_tools.py    # FileOperations usage tests
└── test_example_tools.py # Deterministic calculation tests
```

### Test Fixtures

```python
# conftest.py
import pytest
from fastmcp.client import Client
from mcp_server_core import ServerConfig, MCPServer

@pytest.fixture
def config():
    """Test configuration."""
    return ServerConfig(
        server_name="test-server",
        environment="dev",
        url_allow_private_ips=True,  # For testing
        url_require_https=False      # For testing
    )

@pytest.fixture
async def test_client(config):
    """FastMCP test client with in-memory transport."""
    mcp_server = MCPServer(config)

    # Register tools
    from tools.web_tools import register_web_tools
    from tools.file_tools import register_file_tools
    from tools.example_tools import register_example_tools

    register_web_tools(mcp_server.mcp)
    register_file_tools(mcp_server.mcp)
    register_example_tools(mcp_server.mcp)

    async with Client(mcp_server.mcp) as client:
        yield client
```

### Test Patterns

**Test successful execution:**
```python
async def test_calculate_total_success(test_client):
    result = await test_client.call_tool("calculate_total", {
        "items": [{"price": 10.0, "quantity": 2}]
    })
    assert result.data["total"] == 22.0  # 20 + 2 tax
```

**Test security boundaries:**
```python
async def test_fetch_url_blocks_private_ip(test_client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="private IP"):
        await test_client.call_tool("fetch_url", {
            "url": "http://192.168.1.1"
        })
```

**Test input validation:**
```python
async def test_read_file_validates_path(test_client):
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="outside allowed"):
        await test_client.call_tool("read_file", {
            "file_path": "/etc/passwd"
        })
```

---

## Troubleshooting

### Server Won't Start

**Check configuration:**
```bash
# Verify .env exists
ls -la .env

# Check MCP_SERVER_NAME is set
grep MCP_SERVER_NAME .env
```

**Check virtual environment:**
```bash
# Should show ../.venv/bin/python
which python

# Reinstall if needed
make install-dev
```

### Logs Not Appearing

**STDIO mode:**
```bash
# Check log file location
echo $MCP_LOG_FILE

# Tail logs
tail -f /tmp/mcp-example-server.log
```

**HTTP mode:**
```bash
# Logs should appear in terminal
MCP_TRANSPORT=http python server.py
```

### Security Errors in Development

**Allow private IPs for local testing:**
```bash
# .env
MCP_ENVIRONMENT=dev
MCP_URL_ALLOW_PRIVATE_IPS=true
MCP_URL_REQUIRE_HTTPS=false
```

### Tools Not Found

**Check tool registration:**
```python
# server.py should have:
from tools.web_tools import register_web_tools
from tools.file_tools import register_file_tools
from tools.example_tools import register_example_tools

register_web_tools(mcp_server.mcp)
register_file_tools(mcp_server.mcp)
register_example_tools(mcp_server.mcp)
```

---

## Deployment

### Local Development (STDIO)

```bash
# Run server
make run

# Configure Claude Desktop
# Add to ~/Library/Application Support/Claude/claude_desktop_config.json:
{
  "mcpServers": {
    "example-server": {
      "command": "python",
      "args": ["/path/to/example_server/server.py"],
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

### Cloud Deployment (HTTP)

**Docker:**
```dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install uv && uv pip install .

# Copy application
COPY . .

# Environment
ENV MCP_TRANSPORT=http
ENV MCP_ENVIRONMENT=production
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8000

# Run
CMD ["python", "server.py"]
```

**Environment variables for production:**
```bash
MCP_TRANSPORT=http
MCP_ENVIRONMENT=production
MCP_MASK_ERROR_DETAILS=true
MCP_INCLUDE_TRACEBACK=false
MCP_URL_ALLOW_PRIVATE_IPS=false
MCP_URL_REQUIRE_HTTPS=true
```

---

## Notes for Claude Code

When working with this server:

1. **This is a reference implementation** - Copy patterns, don't modify this server for production use
2. **Security is paramount** - Always use security abstractions for HTTP and file operations
3. **Transport-aware logging** - Never use print() or stdout in STDIO mode
4. **Deterministic tools** - Tools execute precise logic, LLMs orchestrate
5. **Focused tools** - Keep tools simple with ≤3 parameters when possible
6. **Test everything** - Especially security boundaries and error cases
7. **British English** - Honour spelling conventions in docstrings
8. **Use latest versions** - Check for latest stable package versions
9. **Environment variables** - All configuration via .env file

---

**Last Updated:** 28 October 2025
**Server Version:** 0.1.0
