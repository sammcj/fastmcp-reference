# CLAUDE.md - MCP Server Core Package

This file provides guidance to Claude Code when working with the `mcp-server-core` package.

---

## Package Purpose

`mcp-server-core` is a minimal, security-focused foundation for building production-ready MCP (Model Context Protocol) servers. It provides reusable foundational components that wrap FastMCP's built-in features with security abstractions and production-ready patterns.

**Core Principles:**
- Leverage FastMCP built-ins (don't reinvent logging, error handling, middleware)
- Security-first abstractions (SSRF prevention, path traversal protection)
- Transport-aware logging (STDIO file-based, HTTP stdout)
- Minimal dependencies (FastMCP + pydantic-settings)
- Production-ready patterns with sensible defaults

---

## Package Structure

```
mcp_server_core/
├── __init__.py              # Package exports
├── config.py                # Pydantic Settings configuration
├── server.py                # MCPServer with middleware
├── logging.py               # Transport-aware logging setup
├── exceptions.py            # Custom exceptions
├── abstractions/
│   ├── url_fetcher.py       # SSRF prevention for HTTP requests
│   └── file_ops.py          # Path traversal protection for file operations
└── middleware/
    └── factory.py           # Middleware configuration factory
```

---

## Critical Design Decisions

### 1. Leverage FastMCP Built-ins

**NEVER re-implement what FastMCP already provides:**

FastMCP includes production-ready middleware:
- `LoggingMiddleware` / `StructuredLoggingMiddleware`
- `ErrorHandlingMiddleware` / `RetryMiddleware`
- `TimingMiddleware` / `DetailedTimingMiddleware`
- `RateLimitingMiddleware` / `SlidingWindowRateLimitingMiddleware`
- `ResponseCachingMiddleware`

**We use these directly via `middleware/factory.py`.**

```python
# ❌ WRONG - Don't reinvent
class CustomLoggingMiddleware(Middleware):
    async def on_message(self, context, call_next):
        # ... custom logging

# ✅ CORRECT - Use FastMCP built-in
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
```

### 2. Transport-Aware Logging (CRITICAL)

**STDIO mode uses stdout/stderr for the MCP JSON-RPC protocol itself.**

Logging configuration in `logging.py`:
- **STDIO mode:** Logs to file (e.g., `/tmp/mcp-server.log`)
- **HTTP mode:** Logs to stdout (captured by container runtime)

```python
# ❌ WRONG - Breaks STDIO protocol
print("Debug info")
sys.stdout.write("Info")
logging.StreamHandler()  # Goes to stdout!

# ✅ CORRECT - Transport-aware
await ctx.info("Debug info")  # Routed correctly based on transport
```

**This is automatically configured by `setup_logging()` in `logging.py`.**

### 3. Security-First Abstractions

Instead of opinionated business logic abstractions (databases, APIs), we provide **security boundary abstractions**:

**URLFetcher (`abstractions/url_fetcher.py`):**
- Prevents SSRF attacks (blocks private IP ranges)
- Enforces HTTPS in production
- Size limits (10MB default)
- Timeout controls (30s default)

**FileOperations (`abstractions/file_ops.py`):**
- Prevents path traversal (blocks `..`)
- Enforces directory whitelist
- Safe permissions (0600 default - owner read/write only)
- Size limits (100MB default)

These prevent common vulnerabilities while remaining flexible for different use cases.

### 4. Configuration via Environment Variables

**12-factor app pattern using Pydantic Settings (`config.py`):**

All configuration via environment variables with `MCP_` prefix:
- `MCP_SERVER_NAME` (required)
- `MCP_TRANSPORT` (stdio/http)
- `MCP_ENVIRONMENT` (dev/staging/production)
- `MCP_LOG_LEVEL`, `MCP_ALLOWED_FILE_DIRECTORIES`, etc.

**NEVER hardcode configuration values.**

---

## FastMCP Version Context

Built for **FastMCP v2.12.3+**

**Key Features Used:**
- Middleware framework (v2.0+)
- Built-in middleware (logging, error handling, rate limiting, etc.)
- Context-based logging (`ctx.debug()`, `ctx.info()`, etc.)
- In-memory testing transport
- Transport modes: STDIO and HTTP with streaming

**Important:** FastMCP is actively developed. Pin versions in production:
```toml
[project.dependencies]
fastmcp = ">=2.12.3,<3.0.0"
```

---

## Development Workflow

### Using the Makefile

```bash
# Setup (one-time)
make setup        # Create shared .venv at ../. venv

# Development
make install-dev  # Install with dev dependencies
make format       # Format code with ruff
make lint         # Check code style
make test-cov     # Run tests with coverage

# Package
make package      # Build distribution
make clean        # Remove build artifacts
```

### Running Tests

Tests use FastMCP's in-memory transport for fast execution:

```python
from fastmcp.client import Client

async def test_tool():
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("my_tool", {"param": "value"})
        assert result.data == "expected"
```

**Benefits:**
- Millisecond test execution (no network I/O)
- No mocking needed
- Identical to production behaviour

**Coverage targets:**
- Branch coverage enabled
- Minimum 90% coverage
- HTML reports in `coverage/html/`

---

## Critical Anti-Patterns to Avoid

### ⚠️ CRITICAL: STDIO Protocol Violation

**NEVER log to stdout/stderr in STDIO mode:**

```python
# ❌ WRONG - Corrupts MCP protocol
print("Debug")
sys.stdout.write("Info")
logging.basicConfig(stream=sys.stdout)

# ✅ CORRECT - Use Context logging
@mcp.tool
async def my_tool(ctx: Context) -> str:
    await ctx.info("Processing")
    await ctx.debug("Details")
    return "result"
```

### ⚠️ CRITICAL: Hardcoded Configuration

**NEVER hardcode secrets, endpoints, or configuration:**

```python
# ❌ WRONG
DB_URL = "postgresql://user:pass@localhost/db"
API_KEY = "sk-1234567890"

# ✅ CORRECT
config = ServerConfig()  # Loads from environment variables
db_url = config.database_url  # From MCP_DATABASE_URL
```

### ⚠️ CRITICAL: Security Abstraction Bypass

**NEVER bypass the security abstractions:**

```python
# ❌ WRONG - SSRF vulnerable
import requests
response = requests.get(user_url)

# ❌ WRONG - Path traversal vulnerable
with open(user_path, 'rb') as f:
    content = f.read()

# ✅ CORRECT - Use security abstractions
url_fetcher = URLFetcher(http_client, config)
response = await url_fetcher.fetch(user_url)

file_ops = FileOperations(config)
content = await file_ops.read_file(user_path)
```

### ⚠️ HIGH: Sync I/O in Async Context

**NEVER use synchronous I/O in async code:**

```python
# ❌ WRONG - Blocks event loop
time.sleep(1)
response = requests.get(url)
with open(path) as f:
    data = f.read()

# ✅ CORRECT - Use async equivalents
await asyncio.sleep(1)
response = await http_client.get(url)  # httpx
content = await file_ops.read_file(path)  # aiofiles internally
```

### ⚠️ HIGH: Global State

**NEVER use global variables for request state:**

```python
# ❌ WRONG - Race conditions and data leaks
current_user = None

@mcp.tool
async def set_user(user_id: str):
    global current_user
    current_user = user_id  # Shared across all requests!

# ✅ CORRECT - Use Context for request-scoped state
@mcp.tool
async def process(user_id: str, ctx: Context):
    # Context is request-scoped
    await ctx.info(f"Processing for {user_id}")
```

---

## Security Best Practices

### SSRF Prevention

The `URLFetcher` blocks private IP ranges:

```python
# Blocked IPs:
# - 10.0.0.0/8
# - 172.16.0.0/12
# - 192.168.0.0/16
# - 127.0.0.0/8
# - 169.254.0.0/16
# - localhost

url_fetcher = URLFetcher(http_client, config)

# ✅ Safe
await url_fetcher.fetch("https://api.github.com")

# ❌ Blocked - Private IP
await url_fetcher.fetch("http://192.168.1.1")  # SecurityError

# ❌ Blocked - HTTP in production
await url_fetcher.fetch("http://example.com")  # SecurityError if MCP_ENVIRONMENT=production
```

### Path Traversal Protection

The `FileOperations` enforces directory whitelist:

```python
file_ops = FileOperations(config)

# ✅ Safe - Within allowed directory
await file_ops.read_file("/tmp/data.txt")

# ❌ Blocked - Path traversal
await file_ops.read_file("/tmp/../etc/passwd")  # SecurityError

# ❌ Blocked - Outside whitelist
await file_ops.read_file("/etc/passwd")  # SecurityError

# ✅ Safe permissions - Files created with 0600
await file_ops.write_file("/tmp/secret.txt", b"data")
# Created with owner read/write only
```

### Configuration Security

```bash
# Development
MCP_ENVIRONMENT=dev
MCP_MASK_ERROR_DETAILS=false
MCP_INCLUDE_TRACEBACK=true
MCP_URL_ALLOW_PRIVATE_IPS=true  # For local testing
MCP_URL_REQUIRE_HTTPS=false     # For local testing

# Production
MCP_ENVIRONMENT=production
MCP_MASK_ERROR_DETAILS=true
MCP_INCLUDE_TRACEBACK=false
MCP_URL_ALLOW_PRIVATE_IPS=false  # SSRF protection
MCP_URL_REQUIRE_HTTPS=true       # Force HTTPS
```

---

## Configuration Reference

### Server Identity

- `MCP_SERVER_NAME` (required): Server name
- `MCP_ENVIRONMENT`: `dev`, `staging`, `production` (default: `production`)

### Transport & Logging

- `MCP_TRANSPORT`: `stdio`, `http` (default: `stdio`)
- `MCP_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `MCP_LOG_FILE`: Log file path for STDIO mode (default: `/tmp/mcp-{server_name}.log`)
- `MCP_LOG_INCLUDE_PAYLOADS`: Include request/response payloads (default: `false`)

### HTTP Transport (if MCP_TRANSPORT=http)

- `MCP_HTTP_HOST`: Host to bind (default: `0.0.0.0`)
- `MCP_HTTP_PORT`: Port to bind (default: `8000`)

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

---

## Code Style and Standards

### Python Version

- **Target:** Python 3.14+ (latest stable)
- **Minimum:** Python 3.12+

### Dependencies

**Core (minimal):**
- `fastmcp>=2.12.3` (includes httpx, pydantic)
- `pydantic-settings>=2.11`

**Development:**
- `pytest>=8.0`
- `pytest-asyncio>=0.24`
- `pytest-cov>=6.0`
- `ruff>=0.8` (formatting and linting)

### Formatting and Linting

Uses `ruff` for both formatting and linting:

```bash
make format  # Format code
make lint    # Check code style
```

**Ruff configuration in `pyproject.toml`:**
- Line length: 100
- Python 3.12+ target
- British English spelling in docstrings

---

## Testing Guidelines

### Test Organisation

```
tests/
├── test_config.py          # Configuration validation
├── test_logging.py         # Logging setup
├── test_server.py          # Server creation and middleware
├── test_url_fetcher.py     # SSRF prevention
├── test_file_ops.py        # Path traversal protection
└── test_exceptions.py      # Custom exceptions
```

### Test Patterns

**Use FastMCP in-memory transport:**

```python
import pytest
from fastmcp.client import Client
from mcp_server_core import ServerConfig, MCPServer

@pytest.fixture
def config():
    return ServerConfig(
        server_name="test-server",
        environment="dev"
    )

@pytest.fixture
async def test_client(config):
    mcp_server = MCPServer(config)

    @mcp_server.mcp.tool
    def example_tool(data: str) -> str:
        return f"Processed: {data}"

    async with Client(mcp_server.mcp) as client:
        yield client

async def test_tool_execution(test_client):
    result = await test_client.call_tool("example_tool", {"data": "test"})
    assert result.data == "Processed: test"
```

**Test security abstractions:**

```python
import pytest
from mcp_server_core.abstractions import URLFetcher
from mcp_server_core.exceptions import SecurityError

async def test_ssrf_prevention(config, http_client):
    fetcher = URLFetcher(http_client, config)

    # Should block private IPs
    with pytest.raises(SecurityError, match="private IP"):
        await fetcher.fetch("http://192.168.1.1")
```

### Coverage Requirements

- **Minimum:** 90% branch coverage
- **Reports:** HTML (`coverage/html/index.html`), XML (`coverage/coverage.xml`), terminal
- **Run:** `make test-cov`

---

## Common Tasks

### Adding a New Security Abstraction

1. Create module in `abstractions/`
2. Define clear security boundary (what attacks does it prevent?)
3. Add configuration options to `config.py`
4. Write comprehensive tests (positive and negative cases)
5. Document in README.md

Example structure:

```python
# abstractions/new_abstraction.py
from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError

class NewAbstraction:
    """Security abstraction for [purpose].

    Prevents: [security issue]
    """

    def __init__(self, config: ServerConfig):
        self.config = config

    async def safe_operation(self, user_input: str) -> str:
        """Perform operation with security checks."""
        # Validation
        if not self._is_safe(user_input):
            raise SecurityError("Invalid input")

        # Safe operation
        return await self._execute(user_input)
```

### Adding Configuration Options

1. Add field to `ServerConfig` in `config.py`
2. Add environment variable to `.env.example`
3. Document in README.md Configuration Reference
4. Add test for validation in `tests/test_config.py`

```python
# config.py
class ServerConfig(BaseSettings):
    new_option: str = Field(
        default="default_value",
        description="Description of what this configures"
    )

    @field_validator("new_option")
    @classmethod
    def validate_new_option(cls, v: str) -> str:
        """Validate new_option meets requirements."""
        if not v:
            raise ValueError("new_option cannot be empty")
        return v
```

### Updating FastMCP Version

1. Check FastMCP changelog for breaking changes
2. Update version in `pyproject.toml`
3. Run full test suite: `make test-cov`
4. Update code if APIs changed
5. Document any breaking changes

---

## Troubleshooting

### Tests Failing with "Event loop is closed"

**Cause:** Async fixture cleanup issue with pytest-asyncio

**Fix:** Ensure using `pytest-asyncio>=0.24` and `asyncio_mode = "auto"` in `pyproject.toml`

### Import Errors After Installation

**Cause:** Package not in editable mode or wrong Python environment

**Fix:**
```bash
# Verify virtual environment
which python  # Should show ../.venv/bin/python

# Reinstall in editable mode
make install-dev
```

### Coverage Reports Not Generated

**Cause:** pytest-cov configuration issue

**Fix:** Verify `[tool.coverage.run]` in `pyproject.toml` has correct `source` path

### STDIO Logs Not Appearing

**Cause:** Log file path not writable or incorrect configuration

**Fix:**
```bash
# Check log file location
echo $MCP_LOG_FILE  # Default: /tmp/mcp-{server_name}.log

# Verify file permissions
ls -la /tmp/mcp-*.log

# Tail logs
tail -f /tmp/mcp-test-server.log
```

---

## Contributing Guidelines

### Before Making Changes

1. Read this CLAUDE.md file
2. Check existing tests for patterns
3. Ensure FastMCP doesn't already provide the feature
4. Consider security implications

### Making Changes

1. Create feature branch
2. Write tests first (TDD approach)
3. Implement functionality
4. Run `make format && make lint && make test-cov`
5. Ensure 90%+ coverage maintained
6. Update documentation

### Code Review Checklist

- [ ] Tests written and passing
- [ ] Coverage ≥90%
- [ ] No CRITICAL anti-patterns (stdout in STDIO, hardcoded config, security bypass)
- [ ] British English spelling in docstrings
- [ ] Configuration via environment variables
- [ ] Security implications considered
- [ ] Documentation updated

---

## Notes for Claude Code

When working in this package:

1. **Preserve security focus** - Security abstractions are the core value proposition
2. **Never bypass FastMCP built-ins** - Check what FastMCP provides before adding dependencies
3. **Test security boundaries** - Every security feature needs both positive and negative tests
4. **British English** - Honour spelling conventions (organise, analyse, behaviour, colour)
5. **No marketing language** - Keep tone technical and precise
6. **Environment variables only** - Never hardcode configuration
7. **Transport-aware logging** - Remember STDIO can't use stdout/stderr
8. **Use latest package versions** - Always check for latest stable releases
9. **Minimal dependencies** - Only add dependencies if FastMCP doesn't provide the functionality

---

**Last Updated:** 28 October 2025
**Package Version:** 0.1.0
