# FastMCP Built-In Features Reference

**Version:** 1.0
**Date:** 28 October 2025
**Purpose:** Comprehensive guide to FastMCP's built-in capabilities to avoid unnecessary dependencies

---

## ⚠️ CRITICAL: STDIO Transport Warning

**NEVER log directly to stdout/stderr when using STDIO transport mode.**

```python
# ❌ WRONG - Breaks MCP STDIO protocol
print("Processing request")
sys.stdout.write("Debug info")
logging.basicConfig(stream=sys.stdout)  # Breaks STDIO!

# ✅ CORRECT - Use FastMCP's logging
await ctx.info("Processing request")  # Routes correctly based on transport
```

**Why:** STDIO transport uses stdin/stdout for the MCP JSON-RPC protocol itself. Any output to stdout/stderr corrupts the protocol stream and causes client failures.

**Solution:** Always use FastMCP's Context logging methods (`ctx.debug()`, `ctx.info()`, etc.) or configure Python's `logging` to write to files when in STDIO mode.

---

## Table of Contents

1. [Logging Infrastructure](#logging-infrastructure)
2. [Error Handling](#error-handling)
3. [Middleware Framework](#middleware-framework)
4. [Testing Infrastructure](#testing-infrastructure)
5. [Server Composition](#server-composition)
6. [Tool Transformation](#tool-transformation)
7. [Authentication](#authentication)
8. [What You Need External Libraries For](#what-you-need-external-libraries-for)

---

## Logging Infrastructure

### Built-In Logging Middleware

FastMCP provides two production-ready logging middleware options:

#### 1. LoggingMiddleware (Human-Readable)

```python
from fastmcp.server.middleware.logging import LoggingMiddleware

mcp.add_middleware(LoggingMiddleware(
    include_payloads=True,      # Log request/response data
    max_payload_length=1000     # Truncate large payloads
))
```

**Features:**
- Human-readable console output
- Request/response payload logging
- Configurable payload truncation
- Automatic request lifecycle logging

**Use Cases:** Local development, debugging

#### 2. StructuredLoggingMiddleware (JSON)

```python
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware

mcp.add_middleware(StructuredLoggingMiddleware(
    include_payloads=True
))
```

**Features:**
- JSON-formatted output
- Machine-parseable logs
- Compatible with log aggregation tools (CloudWatch, Datadog, ELK)
- Structured metadata

**Use Cases:** Production deployments, cloud environments

### Context Logging Methods

Every tool/resource/prompt receives a `Context` object with logging methods:

```python
@mcp.tool
async def process_data(data: list, ctx: Context) -> dict:
    await ctx.debug("Starting data processing", extra={"count": len(data)})
    await ctx.info("Processing batch", extra={"batch_id": 123})
    await ctx.warning("Data quality issue detected", extra={"issue": "nulls"})
    await ctx.error("Processing failed", extra={"error_code": "E001"})

    return {"status": "complete"}
```

**Methods:**
- `ctx.debug(message, logger_name=None, extra=None)`
- `ctx.info(message, logger_name=None, extra=None)`
- `ctx.warning(message, logger_name=None, extra=None)`
- `ctx.error(message, logger_name=None, extra=None)`

**Key Features:**
- Transport-aware (routes correctly for STDIO/HTTP)
- Structured data via `extra` parameter
- Automatic correlation with requests
- No need for logger instances

### Python Logging Integration

FastMCP integrates with Python's standard `logging` module:

```python
import logging

# Configure Python logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mcp-server.log')  # STDIO mode
        # OR
        # logging.StreamHandler()  # HTTP mode only
    ]
)

# FastMCP middleware will use this configuration
mcp.add_middleware(StructuredLoggingMiddleware())
```

**You DON'T need:**
- ❌ structlog
- ❌ loguru
- ❌ Custom logging libraries

**FastMCP provides sufficient structured logging for production.**

---

## Error Handling

### Built-In Error Handling Middleware

#### 1. ErrorHandlingMiddleware

```python
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

mcp.add_middleware(ErrorHandlingMiddleware(
    include_traceback=True,          # Include stack traces (dev only)
    transform_errors=True,           # Convert errors to MCP format
    error_callback=my_callback       # Custom error handler
))
```

**Features:**
- Comprehensive error logging
- Error transformation to MCP protocol format
- Optional stack traces
- Error statistics tracking
- Custom error callbacks

**Error Statistics:**
```python
middleware = ErrorHandlingMiddleware()
mcp.add_middleware(middleware)

# Later, get error stats
stats = middleware.get_error_stats()
# {"ToolError:call_tool": 5, "ValueError:call_tool": 2}
```

#### 2. RetryMiddleware

```python
from fastmcp.server.middleware.error_handling import RetryMiddleware

mcp.add_middleware(RetryMiddleware(
    max_retries=3,
    retry_exceptions=(ConnectionError, TimeoutError)
))
```

**Features:**
- Automatic retry with exponential backoff
- Configurable retry exceptions
- Maximum retry limit
- Built-in backoff algorithm

### Exception Hierarchy

FastMCP provides a comprehensive exception hierarchy:

```python
from fastmcp.exceptions import (
    FastMCPError,        # Base for all FastMCP errors
    ToolError,           # Tool execution errors
    ResourceError,       # Resource operation errors
    PromptError,         # Prompt operation errors
    ValidationError,     # Parameter validation errors
    ClientError,         # Client operation errors
    NotFoundError,       # Object not found
    DisabledError,       # Object disabled
)
from mcp import McpError  # MCP protocol errors
```

**Error Handling in Tools:**

```python
from fastmcp.exceptions import ToolError

@mcp.tool
def divide(a: float, b: float) -> float:
    if b == 0:
        # ToolError messages are ALWAYS sent to clients
        # (not masked by mask_error_details setting)
        raise ToolError("Division by zero not allowed")

    if not isinstance(a, (int, float)):
        # Standard exceptions can be masked with mask_error_details=True
        raise ValueError("Parameter 'a' must be numeric")

    return a / b
```

**Error Masking:**

```python
# Production: mask internal error details
mcp = FastMCP("Production", mask_error_details=True)

# Development: show full error details
mcp = FastMCP("Development", mask_error_details=False)
```

**You DON'T need:**
- ❌ Custom exception hierarchies
- ❌ Error tracking libraries (built-in stats)
- ❌ Retry libraries (built-in RetryMiddleware)

---

## Middleware Framework

### Complete Middleware System

FastMCP provides a full middleware pipeline with lifecycle hooks:

#### Middleware Hooks

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class CustomMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        """Called for ALL MCP messages."""
        return await call_next(context)

    async def on_request(self, context: MiddlewareContext, call_next):
        """Called for ALL requests."""
        return await call_next(context)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Called for tool invocations."""
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """Called for resource reads."""
        return await call_next(context)

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """Called for prompt requests."""
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """Called for tool listing."""
        return await call_next(context)

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        """Called for resource listing."""
        return await call_next(context)

    async def on_notification(self, context: MiddlewareContext, call_next):
        """Called for notifications."""
        return await call_next(context)
```

### Built-In Middleware

#### TimingMiddleware

```python
from fastmcp.server.middleware.timing import TimingMiddleware, DetailedTimingMiddleware

# Basic timing
mcp.add_middleware(TimingMiddleware())

# Detailed per-operation timing
mcp.add_middleware(DetailedTimingMiddleware())
```

**Output:**
```
Request tools/call completed in 45.23ms
Tool 'get_user' executed in 42.15ms
```

#### RateLimitingMiddleware

```python
from fastmcp.server.middleware.rate_limiting import (
    RateLimitingMiddleware,
    SlidingWindowRateLimitingMiddleware
)

# Token bucket (allows bursts)
mcp.add_middleware(RateLimitingMiddleware(
    max_requests_per_second=10.0,
    burst_capacity=20
))

# Sliding window (precise time-based)
mcp.add_middleware(SlidingWindowRateLimitingMiddleware(
    max_requests=100,
    window_minutes=1
))
```

### Middleware Context

Access request metadata and state:

```python
class AuthMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access request details
        tool_name = context.message.name
        method = context.method  # "tools/call"
        source = context.source  # Client identifier

        # Access FastMCP context
        if context.fastmcp_context:
            tool = await context.fastmcp_context.fastmcp.get_tool(tool_name)

            # Check tool metadata
            if "admin" in tool.tags:
                raise ToolError("Requires admin privileges")

        # Store state for tools
        context.set_state("user_id", "user_123")

        return await call_next(context)
```

**You DON'T need:**
- ❌ Custom middleware frameworks
- ❌ Request pipeline libraries
- ❌ Rate limiting libraries

---

## Testing Infrastructure

### In-Memory Testing

FastMCP provides a fast in-memory transport for testing:

```python
from fastmcp import FastMCP
from fastmcp.client import Client
import pytest

@pytest.fixture
async def test_client():
    mcp = FastMCP("test-server")

    @mcp.tool
    def add(a: int, b: int) -> int:
        return a + b

    async with Client(mcp) as client:
        yield client

async def test_add_tool(test_client: Client):
    result = await test_client.call_tool("add", {"a": 5, "b": 3})
    assert result.data == 8
```

**Features:**
- No network I/O (millisecond test execution)
- Full protocol simulation
- Identical to production behaviour
- Async/await support

**Benefits:**
- 1000+ tests run in seconds (FastMCP repo has 1000+ tests)
- No test doubles or mocks needed
- Integration tests that are fast

**You DON'T need:**
- ❌ pytest-mock (use in-memory transport)
- ❌ responses or httpretty (for HTTP mocking)
- ❌ Custom test harness

---

## Server Composition

### Mounting and Importing Servers

FastMCP supports modular server architecture:

#### Mounting (Live Linking)

```python
# Child server
weather = FastMCP("Weather")

@weather.tool
def get_forecast() -> str:
    return "Sunny"

# Parent server
main = FastMCP("Main")
main.mount(weather, prefix="weather")

# Tool accessible as: weather_get_forecast
```

**Features:**
- Live updates (changes to child reflect immediately)
- Shared lifecycle
- Namespace isolation via prefix

#### Importing (Static Copy)

```python
# Import at a point in time
await main.import_server(weather, prefix="weather")

# Subsequent changes to weather server are NOT reflected
```

**Features:**
- Static snapshot
- Independent lifecycle
- Version locking

### Layered Middleware

```python
# Parent server with global middleware
parent = FastMCP("Parent")
parent.add_middleware(AuthenticationMiddleware())

# Child server with specific middleware
child = FastMCP("Child")
child.add_middleware(LoggingMiddleware())

# Compose
parent.mount(child, prefix="child")

# Requests to child tools go through:
# 1. Parent's AuthenticationMiddleware
# 2. Child's LoggingMiddleware
# 3. Tool execution
```

**You DON'T need:**
- ❌ Service mesh libraries
- ❌ API gateway frameworks
- ❌ Custom composition patterns

---

## Tool Transformation

### Runtime Tool Modification (FastMCP 2.8+)

Transform existing tools to make them LLM-friendly:

```python
from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform

mcp = FastMCP()

# Existing tool from third-party library
from some_library import generic_search

# Transform it
product_search = Tool.from_tool(
    tool=generic_search,
    name="find_products_by_keyword",
    description="Search product catalogue for items matching keyword",
    transform_args={
        "q": ArgTransform(
            name="keyword",
            description="Search term for finding products"
        ),
        "limit": ArgTransform(hide=True, default=10)  # Hide from LLM
    }
)

mcp.add_tool(product_search)
```

**Features:**
- Rewrite descriptions
- Rename parameters
- Hide parameters (provide defaults)
- Wrap with custom logic

### Dynamic Enable/Disable

```python
@mcp.tool(enabled=False)
def legacy_tool():
    """Disabled by default."""
    pass

# Enable/disable at runtime
legacy_tool.enable()
legacy_tool.disable()
```

**You DON'T need:**
- ❌ Tool decorator libraries
- ❌ Parameter transformation frameworks

---

## Authentication

### OAuth Providers (Built-In)

FastMCP includes OAuth authentication for major providers:

```python
from fastmcp import FastMCP

mcp = FastMCP("Authenticated Server")

# Configure OAuth
mcp.auth.configure_oauth(
    provider="google",  # or "github", "azure", "auth0", "workos"
    client_id="your-client-id",
    client_secret="your-client-secret",
    scopes=["openid", "email", "profile"]
)
```

**Supported Providers:**
- Google
- GitHub
- Azure
- Auth0
- WorkOS

**Features:**
- Zero-config client experience
- Automatic token management
- Token refresh handling
- Secure token storage

**Note:** For custom authentication (API keys, JWT), implement via middleware:

```python
class APIKeyAuthMiddleware(Middleware):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def on_request(self, context: MiddlewareContext, call_next):
        # Extract API key from context/headers
        provided_key = context.get_state("api_key")

        if provided_key != self.api_key:
            raise ToolError("Invalid API key")

        return await call_next(context)
```

**You DON'T need:**
- ❌ authlib
- ❌ python-jose (for JWT)
- ❌ OAuth client libraries

---

## What You Need External Libraries For

FastMCP does NOT provide:

### 1. Configuration Management
**Need:** `pydantic-settings`

```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    server_name: str
    log_level: str = "INFO"
```

### 2. Observability (OpenTelemetry/Prometheus)
**Need:**
- `opentelemetry-api`
- `opentelemetry-sdk`
- `prometheus-client`

FastMCP provides timing middleware but not distributed tracing or metrics export.

### 3. Security Abstractions
**Need:**
- SSRF prevention (use `httpx` with validation)
- Path traversal protection (standard library + validation)
- Code sandboxing (`llm-sandbox`)

### 4. Database Clients
**Need:**
- `asyncpg` (PostgreSQL)
- `redis` (Redis)
- `sqlalchemy` (if using ORM)

FastMCP is database-agnostic.

### 5. HTTP Client
**Actually included:** FastMCP depends on `httpx`, so you already have it.

```python
# httpx is available
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get("https://api.example.com")
```

---

## Summary: Minimal External Dependencies

For a production MCP platform package, you only need:

**Core Dependencies:**
```toml
[project]
dependencies = [
    "fastmcp>=2.9.0",           # Everything above
    "pydantic-settings>=2.0",   # Config management
]
```

**Optional Dependencies:**
```toml
[project.optional-dependencies]
observability = [
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
    "prometheus-client>=0.19",
]
security = [
    "llm-sandbox>=0.1.0",
]
```

**Everything else (logging, error handling, middleware, testing, rate limiting, timing, composition) is built into FastMCP.**

---

## Best Practices

### 1. Always Use Context Logging

```python
# ✅ CORRECT
@mcp.tool
async def process(data: str, ctx: Context) -> str:
    await ctx.info("Processing started")
    return f"Processed: {data}"

# ❌ WRONG (breaks STDIO)
@mcp.tool
async def process(data: str, ctx: Context) -> str:
    print("Processing started")  # Breaks STDIO transport!
    return f"Processed: {data}"
```

### 2. Use Built-In Middleware

```python
# ✅ CORRECT - Use FastMCP's built-ins
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

mcp.add_middleware(ErrorHandlingMiddleware())
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(StructuredLoggingMiddleware())

# ❌ WRONG - Don't reinvent the wheel
class MyCustomLoggingMiddleware(Middleware):  # Unnecessary!
    async def on_message(self, context, call_next):
        # ... custom logging logic FastMCP already provides
```

### 3. Use FastMCP Exceptions

```python
# ✅ CORRECT
from fastmcp.exceptions import ToolError, ValidationError

@mcp.tool
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ToolError("Division by zero")  # Always sent to client
    return a / b

# ❌ WRONG
@mcp.tool
def divide(a: float, b: float) -> float:
    if b == 0:
        raise Exception("Division by zero")  # May be masked
    return a / b
```

### 4. Leverage In-Memory Testing

```python
# ✅ CORRECT - Fast integration tests
async def test_tool():
    mcp = FastMCP("test")

    @mcp.tool
    def add(a: int, b: int) -> int:
        return a + b

    async with Client(mcp) as client:
        result = await client.call_tool("add", {"a": 1, "b": 2})
        assert result.data == 3

# ❌ WRONG - Slow, complex mocking
@mock.patch('requests.post')
def test_tool(mock_post):
    mock_post.return_value = ...  # Complex setup
    # ... slow test with network simulation
```

---

## Configuration Example

Complete server setup using only FastMCP built-ins:

```python
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware,
    RetryMiddleware
)
from fastmcp.server.middleware.timing import DetailedTimingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
import logging

# Configure Python logging for transport mode
def configure_logging(transport: str, log_file: str = "/tmp/mcp.log"):
    if transport == "stdio":
        # STDIO: log to file
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            handlers=[logging.FileHandler(log_file)]
        )
    else:
        # HTTP: log to stdout
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            handlers=[logging.StreamHandler()]
        )

# Create server
configure_logging(transport="stdio")

mcp = FastMCP("Production Server", mask_error_details=True)

# Add middleware stack (order matters)
mcp.add_middleware(ErrorHandlingMiddleware(
    include_traceback=False,  # Production
    transform_errors=True
))
mcp.add_middleware(RetryMiddleware(
    max_retries=3,
    retry_exceptions=(ConnectionError, TimeoutError)
))
mcp.add_middleware(RateLimitingMiddleware(
    max_requests_per_second=10.0,
    burst_capacity=20
))
mcp.add_middleware(DetailedTimingMiddleware())
mcp.add_middleware(StructuredLoggingMiddleware(include_payloads=False))

@mcp.tool
async def example_tool(data: str, ctx: Context) -> str:
    await ctx.info("Processing request", extra={"data_length": len(data)})
    return f"Processed: {data}"

# Run server
if __name__ == "__main__":
    mcp.run(transport="stdio")  # or "http"
```

**This configuration uses ZERO external dependencies beyond FastMCP itself.**

---

## Version Information

**Document Version:** 1.0
**FastMCP Version Documented:** 2.9.0+
**Last Updated:** 28 October 2025

**Key Version Changes:**
- FastMCP 2.8: Added tool transformation, tag-based filtering, enable/disable
- FastMCP 2.9: Enhanced middleware, structured logging improvements

---

## References

- [FastMCP Official Documentation](https://gofastmcp.com)
- [FastMCP GitHub Repository](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io)
- [FastMCP 2.8 Release Notes](https://www.jlowin.dev/blog/fastmcp-2-8-tool-transformation)

---

**Key Takeaway:** FastMCP is a batteries-included framework. Before adding any external dependency, check if FastMCP already provides the functionality. Most of the time, it does.
