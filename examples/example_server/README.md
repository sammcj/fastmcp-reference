# Example MCP Server

Reference implementation demonstrating `mcp-server-core` usage with production-ready patterns.

## Overview

This server demonstrates:
- Using `mcp-server-core` for configuration and security
- FastMCP built-in middleware (logging, error handling, rate limiting, retry, timing)
- Security abstractions (SSRF prevention, path traversal protection)
- Transport-aware logging (STDIO file-based, HTTP stdout)
- AI Precision Anti-Pattern avoidance (deterministic calculations in tools)

## Quick Start

### Prerequisites

Install `uv` (fast Python package installer):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup and Run

```bash
# From parent examples directory, set up shared .venv (one-time)
cd ../mcp_server_core
make setup

# Install example server with dev dependencies
cd ../example_server
make install-dev

# Run the server (STDIO mode)
make run
```

That's it! The Makefile handles configuration setup and server execution.

### Manual Setup (Alternative)

If you prefer manual setup without Make:

```bash
# Create virtual environment
cd examples
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ./mcp_server_core
uv pip install -e ./example_server

# Configure
cd example_server
cp .env.example .env

# Run server
python server.py
```

## Available Tools

### Web Tools (SSRF Prevention)

#### `fetch_url`
Fetch content from a URL with security checks.

```python
# Example usage
fetch_url(url="https://api.github.com")
```

**Security features:**
- Blocks private IP ranges (10.x.x.x, 192.168.x.x, 127.x.x.x, etc.)
- HTTPS enforcement (in production)
- Size limits (10MB default)
- Timeout controls (30s default)

#### `fetch_json`
Fetch and parse JSON with security checks.

```python
# Example usage
fetch_json(url="https://api.github.com/users/octocat")
```

### File Tools (Path Traversal Protection)

#### `read_file`
Read file with directory whitelist.

```python
# Example usage
read_file(file_path="/tmp/data.txt")
```

**Security features:**
- Only allowed directories (`/tmp`, `./data` by default)
- Path traversal prevention (blocks `..`)
- Size limits (100MB default)

#### `write_file`
Write file with safe permissions.

```python
# Example usage
write_file(file_path="/tmp/output.txt", content="Hello, World!")
```

**Security features:**
- Only allowed directories
- Automatic safe permissions (0600 - owner read/write only)
- Path traversal prevention
- Size limits

#### `list_directory`
List files in directory.

```python
# Example usage
list_directory(dir_path="/tmp")
```

### Example Tool (AI Precision Anti-Pattern Avoidance)

#### `calculate_total`
Calculate order total using deterministic arithmetic.

```python
# Example usage
calculate_total(items=[
    {"name": "Widget", "price": 10.50, "quantity": 2},
    {"name": "Gadget", "price": 5.25, "quantity": 3}
])

# Returns:
# {
#     "subtotal": 36.75,
#     "tax": 3.68,
#     "total": 40.43,
#     "item_count": 2
# }
```

**Why this pattern?**
- LLM orchestrates (calls the tool)
- Tool executes precise calculations
- Never ask LLM to do maths (AI Precision Anti-Pattern)

## Configuration

See `.env.example` for all available configuration options.

### Key Settings

**Transport Mode:**
```bash
# STDIO (local development, Claude Desktop)
MCP_TRANSPORT=stdio
MCP_LOG_FILE=/tmp/mcp-example-server.log

# HTTP (cloud deployment, container)
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8000
```

**Security:**
```bash
# File operations
MCP_ALLOWED_FILE_DIRECTORIES=["/tmp", "./data"]
MCP_MAX_FILE_SIZE_MB=100

# URL fetching
MCP_URL_ALLOW_PRIVATE_IPS=false  # SSRF protection
MCP_URL_REQUIRE_HTTPS=true       # Force HTTPS
```

**Error Handling:**
```bash
# Development
MCP_MASK_ERROR_DETAILS=false
MCP_INCLUDE_TRACEBACK=true

# Production
MCP_MASK_ERROR_DETAILS=true
MCP_INCLUDE_TRACEBACK=false
```

## Testing

```bash
# Run tests with coverage
make test-cov

# Run tests without coverage
make test

# Format and lint code
make format
make lint
```

Example test using in-memory transport:

```python
from fastmcp.client import Client

async def test_calculate_total():
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("calculate_total", {
            "items": [{"price": 10, "quantity": 2}]
        })
        assert result.data["total"] == 22.0  # 20 + 2 tax
```

## Deployment

### Local Development (STDIO)

```bash
# Run with STDIO transport (for Claude Desktop)
python server.py
```

**Log location:** `/tmp/mcp-example-server.log`

### Cloud Deployment (HTTP)

```bash
# Run with HTTP transport
MCP_TRANSPORT=http python server.py
```

**Logs:** stdout (captured by container runtime → CloudWatch/Datadog)

### Docker Example

```dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install uv && uv pip install .

# Copy application
COPY . .

# Run server
ENV MCP_TRANSPORT=http
ENV MCP_ENVIRONMENT=production
CMD ["python", "server.py"]
```

## Architecture

```
example_server/
├── server.py              # Main server entry point
├── tools/
│   ├── web_tools.py       # URLFetcher usage
│   └── file_tools.py      # FileOperations usage
├── tests/                 # FastMCP in-memory tests
├── .env.example           # Configuration template
└── README.md

Uses:
  mcp_server_core/            # Foundational server components
  └── abstractions/        # Security abstractions
      ├── url_fetcher.py   # SSRF prevention
      └── file_ops.py      # Path traversal protection
```

## Security Features Demonstrated

### 1. SSRF Prevention (URLFetcher)

```python
# Blocks private IPs
fetch_url("http://192.168.1.1")  # ❌ SecurityError

# Requires HTTPS in production
fetch_url("http://example.com")  # ❌ SecurityError (if MCP_ENVIRONMENT=production)

# Enforces size limits
fetch_url("https://huge-file.com")  # ❌ SecurityError (if >10MB)
```

### 2. Path Traversal Protection (FileOperations)

```python
# Blocks path traversal
read_file("/tmp/../etc/passwd")  # ❌ SecurityError

# Enforces directory whitelist
read_file("/etc/passwd")  # ❌ SecurityError (not in allowed directories)

# Safe permissions automatically applied
write_file("/tmp/secret.txt", "data")  # ✅ Created with 0600 (owner only)
```

### 3. AI Precision Anti-Pattern Avoidance

```python
# ❌ WRONG: LLM doing calculations
"Calculate 123.45 * 0.10 for me"  # Unreliable!

# ✅ CORRECT: Deterministic tool
calculate_total([{"price": 123.45, "quantity": 1}])  # Precise!
```

## Middleware Stack

Automatically configured by `mcp-server-core`:

1. **ErrorHandlingMiddleware** - Catches and logs all errors
2. **RetryMiddleware** - Retries transient failures (3 attempts)
3. **RateLimitingMiddleware** - Token bucket (10 req/s, burst 20)
4. **DetailedTimingMiddleware** - Performance monitoring
5. **StructuredLoggingMiddleware** - JSON logging (transport-aware)

All using FastMCP's built-in middleware - no custom implementations needed!

## Best Practices Demonstrated

### 1. Transport-Aware Logging

```python
# STDIO mode: Logs to file
# HTTP mode: Logs to stdout

# NEVER:
print("Debug info")  # ❌ Breaks STDIO protocol!

# ALWAYS:
await ctx.info("Debug info")  # ✅ Routes correctly
```

### 2. Use Security Abstractions

```python
# NEVER:
response = requests.get(user_url)  # ❌ SSRF vulnerable!
open(user_path, 'rb')  # ❌ Path traversal vulnerable!

# ALWAYS:
response = await url_fetcher.fetch(user_url)  # ✅ SSRF protected
content = await file_ops.read_file(user_path)  # ✅ Path protected
```

### 3. Deterministic Tools

```python
# LLM role: Orchestration
# Tool role: Precise execution

# LLM decides: "User wants order total"
# LLM calls: calculate_total(items)
# Tool executes: Precise arithmetic
```

## Troubleshooting

### Logs not appearing?

**STDIO mode:** Check log file location
```bash
tail -f /tmp/mcp-example-server.log
```

**HTTP mode:** Logs go to stdout
```bash
# Should see logs in terminal
python server.py
```

### SecurityError: Path outside allowed directories?

Add directory to whitelist in `.env`:
```bash
MCP_ALLOWED_FILE_DIRECTORIES=["/tmp", "./data", "/your/custom/path"]
```

### SecurityError: URL resolves to private IP?

Enable private IPs in dev (disable in production):
```bash
MCP_URL_ALLOW_PRIVATE_IPS=true  # Dev only!
```

## References

- [mcp-server-core README](../mcp_server_core/README.md)
- [FastMCP Built-in Features](../../research/fastmcp-builtin-features.md)
- [FastMCP Documentation](https://gofastmcp.com)
