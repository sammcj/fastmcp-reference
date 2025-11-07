# FastMCP Technical Architecture Document

**Version:** 1.0
**Date:** 28 October 2025
**Audience:** Engineering Team
**Purpose:** Implementation reference for building foundational MCP components

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Breakdown](#component-breakdown)
3. [Implementation Patterns Catalogue](#implementation-patterns-catalogue)
4. [Configuration Strategy](#configuration-strategy)
5. [Error Handling](#error-handling)
6. [Testing Strategy](#testing-strategy)
7. [Security Model](#security-model)
8. [Performance Considerations](#performance-considerations)
9. [Deployment Model](#deployment-model)
10. [Migration Path](#migration-path)
11. [Comparison Matrices](#comparison-matrices)

---

## Architecture Overview

### Layered Architecture

FastMCP follows a clean layered architecture that separates concerns and enables modular composition:

```mermaid
graph TB
    subgraph "Application Layer"
        A[Tools/Resources/Prompts]
    end

    subgraph "Framework Layer"
        B[FastMCP Server]
        C[Middleware Pipeline]
        D[Context Manager]
    end

    subgraph "Protocol Layer"
        E[MCP Protocol Handler]
        F[Transport Layer]
    end

    subgraph "Infrastructure Layer"
        G[Authentication]
        H[Storage Backends]
        I[Observability]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    F --> H
    F --> I

    classDef app fill:#E6F3FF,stroke:#4A90E2,color:#000
    classDef framework fill:#E8F5E8,stroke:#27AE60,color:#000
    classDef protocol fill:#F0E6FF,stroke:#8E44AD,color:#000
    classDef infra fill:#FFF0E6,stroke:#E67E22,color:#000

    class A app
    class B,C,D framework
    class E,F protocol
    class G,H,I infra
```

### Key Architectural Principles

1. **Decorator-Based API**: Minimal boilerplate using Python decorators
2. **Dependency Injection**: Context automatically injected via type hints
3. **Middleware Pipeline**: Cross-cutting concerns handled uniformly
4. **Transport Agnostic**: STDIO and HTTP (with streaming) supported identically
5. **Composition Over Inheritance**: Server mounting and importing patterns

### Component Responsibilities

| Layer              | Components                   | Responsibilities                                                  |
|--------------------|------------------------------|-------------------------------------------------------------------|
| **Application**    | Tools, Resources, Prompts    | Business logic, domain operations                                 |
| **Framework**      | FastMCP, Middleware, Context | Request routing, lifecycle management, cross-cutting concerns     |
| **Protocol**       | MCP Handler, Transport       | Protocol compliance, message serialisation, connection management |
| **Infrastructure** | Auth, Storage, Observability | Security, persistence, monitoring                                 |

**Source:** FastMCP Official Documentation (Quality: A), Confidence: HIGH

---

## Component Breakdown

### 1. FastMCP Server Core

The central orchestrator managing tools, resources, prompts, and server lifecycle.

**Core Responsibilities:**
- Component registration and discovery
- Request routing and delegation
- Middleware pipeline execution
- Transport protocol management
- Server composition (mounting/importing)

**Key API:**
```python
from fastmcp import FastMCP

# Initialisation
mcp = FastMCP(
    name="MyServer",
    version="1.0.0",
    instructions="Server description for LLMs",
    auth=None,  # Optional authentication provider
    middleware=[],  # Middleware pipeline
)

# Component registration
@mcp.tool
@mcp.resource(uri="...")
@mcp.prompt

# Server composition
await mcp.import_server(subserver, prefix="sub")  # Static copy
mcp.mount(subserver, prefix="sub")  # Live link

# Execution
mcp.run(transport="stdio|http", host="...", port=...)
```

**Design Patterns:**
- **Facade Pattern**: Simplifies complex protocol interactions
- **Decorator Pattern**: Clean API for component registration
- **Strategy Pattern**: Pluggable transport and auth providers

**Source:** FastMCP GitHub README, Official Docs (Quality: A), Confidence: HIGH

---

### 2. Middleware System

> **⚠️ IMPORTANT: FastMCP Provides Production-Ready Middleware**
>
> FastMCP includes built-in, battle-tested implementations of all core middleware (logging, error handling, timing, rate limiting, retry, caching). **Do not build custom implementations of these patterns** - use FastMCP's built-ins directly.
>
> Custom middleware should only be created for domain-specific concerns such as:
> - Authentication/authorisation (business-specific)
> - Custom metrics/observability (company-specific tooling)
> - Domain-specific request transformation
>
> See [`fastmcp-builtin-features.md`](./fastmcp-builtin-features.md) for comprehensive documentation of FastMCP's built-in capabilities.

FastMCP's middleware provides a pipeline model for cross-cutting concerns, inspired by web frameworks but adapted for MCP protocol specifics.

**Architecture:**
```mermaid
graph LR
    A[Client Request] --> B[Middleware 1]
    B --> C[Middleware 2]
    C --> D[Middleware N]
    D --> E[Handler]
    E --> F[Middleware N]
    F --> G[Middleware 2]
    G --> H[Middleware 1]
    H --> I[Client Response]

    classDef middleware fill:#E8F5E8,stroke:#27AE60,color:#000
    classDef handler fill:#F0E6FF,stroke:#8E44AD,color:#000

    class B,C,D,F,G,H middleware
    class E handler
```

**Hook Hierarchy** (from general to specific):
1. `on_message` - All MCP messages
2. `on_request` / `on_notification` - Request type specific
3. Operation-specific:
   - `on_call_tool`
   - `on_read_resource`
   - `on_get_prompt`
   - `on_list_tools`
   - `on_list_resources`
   - `on_list_prompts`
4. `on_initialize` - Client connection initialisation

**Hook Execution Flow:**
For a single tool call, multiple hooks fire:
1. `on_message` (because it's an MCP message)
2. `on_request` (because tool calls expect responses)
3. `on_call_tool` (operation-specific)

This hierarchy enables precise targeting: use `on_message` for broad logging, `on_request` for authentication, `on_call_tool` for tool-specific logic.

**FastMCP Built-in Middleware (Use These):**

| Middleware                              | Purpose                          | Import From                                           | Configuration                                |
|-----------------------------------------|----------------------------------|-------------------------------------------------------|----------------------------------------------|
| **LoggingMiddleware**                   | Human-readable logging           | `fastmcp.server.middleware.logging`                   | Include payloads, max payload length         |
| **StructuredLoggingMiddleware**         | JSON logging (production)        | `fastmcp.server.middleware.logging`                   | Structured format for log aggregation        |
| **ErrorHandlingMiddleware**             | Error logging & transformation   | `fastmcp.server.middleware.error_handling`            | Traceback, callbacks, statistics             |
| **RetryMiddleware**                     | Automatic retry with backoff     | `fastmcp.server.middleware.error_handling`            | Max retries, retry exceptions                |
| **TimingMiddleware**                    | Basic request timing             | `fastmcp.server.middleware.timing`                    | Logs execution duration                      |
| **DetailedTimingMiddleware**            | Per-operation timing             | `fastmcp.server.middleware.timing`                    | Detailed performance monitoring              |
| **RateLimitingMiddleware**              | Token bucket rate limiting       | `fastmcp.server.middleware.rate_limiting`             | Requests/second, burst capacity              |
| **SlidingWindowRateLimitingMiddleware** | Sliding window rate limiting     | `fastmcp.server.middleware.rate_limiting`             | Max requests, window duration                |

**Usage Example:**
```python
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware,
    RetryMiddleware
)
from fastmcp.server.middleware.timing import TimingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

mcp = FastMCP("Production Server")

# Add FastMCP's built-in middleware
mcp.add_middleware(ErrorHandlingMiddleware(include_traceback=False))
mcp.add_middleware(RetryMiddleware(max_retries=3))
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=10))
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(StructuredLoggingMiddleware())
```

**When to Create Custom Middleware:**
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class AuthMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        # Pre-processing: check auth
        if not self._is_authorised(context):
            raise ToolError("Unauthorised")

        # Continue chain
        result = await call_next(context)

        # Post-processing: add metadata
        return result
```

**State Management Pattern:**
```python
class StatefulMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        # Set state accessible to tools via Context
        if context.fastmcp_context:
            context.fastmcp_context.set_state("user_id", "123")

        return await call_next(context)
```

**Component Access Pattern:**
```python
class TagBasedMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access component metadata during execution
        if context.fastmcp_context:
            try:
                tool = await context.fastmcp_context.fastmcp.get_tool(
                    context.message.name
                )
                if "private" in tool.tags:
                    raise ToolError("Access denied: private tool")
            except Exception:
                pass

        return await call_next(context)
```

**Middleware Ordering:**
Execution order matters. Authentication before logging, logging before caching:
```python
mcp.add_middleware(AuthMiddleware())        # First: auth
mcp.add_middleware(TimingMiddleware())      # Second: performance
mcp.add_middleware(LoggingMiddleware())     # Third: logging
mcp.add_middleware(ResponseCachingMiddleware())  # Last: caching
```

**Server Composition + Middleware:**
Parent middleware runs for all requests, mounted server middleware only for routes to that server:
```python
parent = FastMCP("Parent")
parent.add_middleware(AuthMiddleware())  # Applies to all

child = FastMCP("Child")
child.add_middleware(LoggingMiddleware())  # Only for child routes

parent.mount(child, prefix="child")
```

**Source:** FastMCP Middleware Docs (Quality: A), Confidence: HIGH
**Version:** New in v2.9.0, subject to breaking changes

---

### 3. Context System

The Context object provides tools/resources/prompts access to MCP session capabilities and server state.

**Capabilities:**

| Capability             | Methods                                     | Use Case                            |
|------------------------|---------------------------------------------|-------------------------------------|
| **Logging**            | `debug()`, `info()`, `warning()`, `error()` | Send messages to client             |
| **LLM Sampling**       | `sample(messages, **kwargs)`                | Request LLM completions from client |
| **User Elicitation**   | `elicit(prompt, response_type)`             | Request user input interactively    |
| **Progress Reporting** | `report_progress(progress, total)`          | Update on long operations           |
| **Resource Access**    | `list_resources()`, `read_resource(uri)`    | Access registered resources         |
| **Prompt Access**      | `list_prompts()`, `get_prompt(name, args)`  | Access registered prompts           |
| **State Management**   | `set_state(key, value)`, `get_state(key)`   | Share data within request           |
| **Server Access**      | `fastmcp` property                          | Access server instance              |
| **Request Metadata**   | `request_id`, `client_id`                   | Request tracking                    |
| **HTTP Context**       | `http_request`, `headers`, `access_tokens`  | HTTP-specific data                  |

**Dependency Injection Pattern:**
```python
from fastmcp import FastMCP, Context

mcp = FastMCP("Demo")

@mcp.tool
async def process_file(file_uri: str, ctx: Context) -> str:
    # Context automatically injected via type hint
    await ctx.info(f"Processing {file_uri}")

    # Read resource from server
    resource = await ctx.read_resource(file_uri)

    # Report progress
    await ctx.report_progress(50, 100)

    # Use client's LLM
    summary = await ctx.sample(f"Summarise: {resource}")

    return summary.text
```

**Runtime Dependency Function Pattern** (v2.2.11+):
```python
from fastmcp.server.dependencies import get_context

# Utility function that needs context but doesn't receive it as parameter
async def log_operation(message: str):
    ctx = get_context()  # Retrieves active context
    await ctx.info(message)

@mcp.tool
async def my_tool(data: str) -> str:
    await log_operation("Starting operation")
    return process(data)
```

**State Management for Middleware Integration:**
```python
# In middleware
class AuthMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        if context.fastmcp_context:
            context.fastmcp_context.set_state("user_id", extract_user_id())
        return await call_next(context)

# In tool
@mcp.tool
async def get_user_data(ctx: Context) -> dict:
    user_id = ctx.get_state("user_id", default=None)
    if not user_id:
        raise ToolError("User not authenticated")
    return fetch_user_data(user_id)
```

**Context Scoping:**
- Each MCP request receives a **new** Context object
- State set in one request is **not** available in subsequent requests
- Context only available during request execution
- For cross-request persistence, use external storage (database, cache)

**Source:** FastMCP Context Docs (Quality: A), Confidence: HIGH

---

### 4. Server Composition Patterns

FastMCP supports two composition approaches for building modular architectures:

#### Importing (Static Composition)

**Use When:**
- Bundling finalised components
- Performance is critical (no runtime delegation overhead)
- Components won't change after assembly
- Building a distribution package

**Pattern:**
```python
from fastmcp import FastMCP

# Create subservers
weather = FastMCP("Weather")
@weather.tool
def get_forecast(city: str) -> dict:
    return {"city": city, "temp": 22}

database = FastMCP("Database")
@database.resource("data://stats")
def get_stats() -> dict:
    return {"requests": 1000}

# Import into main server
main = FastMCP("Main")
await main.import_server(weather, prefix="weather")
await main.import_server(database, prefix="db")

# Result:
# - Tool: "weather_get_forecast"
# - Resource: "data://db/stats"
```

**Component Prefixing Rules:**
- Tools: `{prefix}_{tool_name}`
- Resources: `{scheme}://{prefix}/{path}`
- Resource Templates: `{scheme}://{prefix}/{template_params}`
- Prompts: `{prefix}_{prompt_name}`

**Without Prefix** (v2.9.0+):
```python
await main.import_server(weather)  # No prefix, original names preserved
```

**Conflict Resolution:**
When multiple servers imported with same prefix, most recently imported takes precedence.

#### Mounting (Live Linking)

**Use When:**
- Components will change at runtime
- Need dynamic tool addition/removal
- Building plugin architectures
- Delegating to remote servers (via proxy)

**Pattern:**
```python
dynamic = FastMCP("Dynamic")

@dynamic.tool
def initial_tool() -> str:
    return "Initial"

# Mount subserver
main = FastMCP("Main")
main.mount(dynamic, prefix="dynamic")

# Add tool AFTER mounting - immediately available
@dynamic.tool
def added_later() -> str:
    return "Added dynamically!"

# Result: Both tools accessible through main server
```

**Performance Consideration:**
Mounting introduces runtime delegation overhead. Server performance affected by slowest mounted server.

**Without Prefix** (v2.9.0+):
```python
main.mount(dynamic)  # No prefix, original names preserved
```

**Middleware with Composition:**
Parent middleware applies to all requests (including routed to children). Child middleware only applies to that child's routes.

**Source:** FastMCP Composition Docs (Quality: A), Confidence: HIGH

---

### 5. Authentication & Authorisation

FastMCP provides enterprise-grade OAuth integration with zero-config client experience.

**Built-in OAuth Providers:**
- Google OAuth
- GitHub OAuth
- Microsoft Azure Active Directory
- Auth0
- WorkOS (enterprise SSO)
- Descope
- Custom JWT/OIDC

**Server-Side Protection Pattern:**
```python
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

auth = GoogleProvider(
    client_id="your-client-id.apps.googleusercontent.com",
    client_secret="your-secret",
    base_url="https://myserver.com",
    allowed_domains=["example.com"]  # Restrict to organisation
)

mcp = FastMCP("Protected", auth=auth)

@mcp.tool
def sensitive_operation(data: str) -> str:
    # Only authenticated users can call this
    return f"Processed: {data}"

mcp.run(transport="http", port=8000)
```

**Client-Side Zero-Config Pattern:**
```python
from fastmcp import Client

async with Client("https://protected-server.com/mcp", auth="oauth") as client:
    # Automatic browser-based OAuth flow
    # Handles token storage, refresh, callbacks
    result = await client.call_tool("sensitive_operation", {"data": "test"})
```

**Token-Based Authentication:**
```python
from fastmcp.server.auth import StaticTokenVerifier

auth = StaticTokenVerifier(
    tokens={"secret-token-123": {"user_id": "admin", "role": "admin"}}
)

mcp = FastMCP("API", auth=auth)
```

**Custom JWT Verification:**
```python
from fastmcp.server.auth import JWTVerifier

auth = JWTVerifier(
    issuer="https://auth.example.com",
    audience="my-mcp-server",
    jwks_uri="https://auth.example.com/.well-known/jwks.json"
)
```

**Authorisation in Middleware:**
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

class RoleBasedAuthMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access user from auth context
        user = context.fastmcp_context.access_tokens.get("user")

        tool_name = context.message.name

        # Enforce role-based access
        if tool_name.startswith("admin_") and user.get("role") != "admin":
            raise ToolError("Admin access required")

        return await call_next(context)
```

**Production Features:**
- Persistent token storage
- Automatic token refresh
- Dynamic Client Registration (DCR) with OAuth proxy pattern
- Environment variable support for credentials
- Local callback server for browser flow

**Source:** FastMCP Auth Docs, Security Articles (Quality: A/B+), Confidence: HIGH

---

### 6. Storage Backends

FastMCP provides pluggable storage for caching and session state.

**Built-in Storage Options:**

| Backend | Use Case | Configuration |
|---------|----------|---------------|
| **In-Memory** | Development, non-persistent cache | Default, no config |
| **Disk (DiskStore)** | Persistent local cache | `directory="cache"` |
| **Redis (RedisStore)** | Distributed deployments | `host`, `port`, `db` |
| **DynamoDB** | AWS cloud deployments | AWS credentials |
| **Custom** | Specific requirements | Implement `KeyValueStore` interface |

**Configuration Pattern:**
```python
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from key_value.aio.stores.redis import RedisStore

# Redis for distributed caching
cache_storage = RedisStore(
    host="redis.example.com",
    port=6379,
    db=0
)

mcp.add_middleware(ResponseCachingMiddleware(
    cache_storage=cache_storage,
    list_tools_settings=ListToolsSettings(ttl=30),
    call_tool_settings=CallToolSettings(
        included_tools=["expensive_operation"]
    )
))
```

**Cache Statistics:**
```python
middleware = ResponseCachingMiddleware()
mcp.add_middleware(middleware)

# Retrieve statistics
stats = middleware.statistics()
print(f"Cache hits: {stats.hits}, misses: {stats.misses}")
```

**Source:** FastMCP Storage Backends Docs (Quality: A), Confidence: HIGH

---

## Implementation Patterns Catalogue

### Pattern 1: In-Memory Testing

**Intent:** Test MCP servers without network or process overhead

**Problem:** Testing MCP servers typically requires starting separate processes, managing connections, and dealing with network issues.

**Solution:** Use `FastMCPTransport` to connect client directly to server instance in memory.

**Code Example:**
```python
import pytest
from fastmcp import FastMCP, Client

# Define server
mcp = FastMCP("TestServer")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# Test fixture
@pytest.fixture
async def test_client():
    async with Client(mcp) as client:
        yield client

# Test
async def test_add_tool(test_client: Client):
    result = await test_client.call_tool("add", {"a": 5, "b": 3})
    assert result.data == 8
```

**Trade-offs:**
- ✅ **Advantages:** Fast, no process management, no network issues, easy debugging
- ❌ **Disadvantages:** Doesn't test transport layer, network serialisation, or multi-process scenarios
- 📊 **Complexity:** Low

**When to Use:**
- Unit testing individual tools/resources
- TDD development workflow
- CI/CD pipeline tests (fast feedback)

**When NOT to Use:**
- Testing transport-specific behaviour (HTTP headers, streaming)
- Load testing or performance testing
- Multi-client scenarios

**Related Patterns:** Integration Testing with Docker, Contract Testing

**Real-World Examples:** FastMCP test suite (1000+ tests using this pattern)

**Sources:** FastMCP Testing Docs, MCPCat Testing Guide (Quality: A/B+)
**Confidence:** HIGH

---

### Pattern 2: Middleware for Cross-Cutting Concerns

**Intent:** Handle authentication, logging, rate limiting, and caching uniformly across all tools/resources

**Problem:** Every tool shouldn't implement its own auth checks, logging, rate limiting, etc. This leads to inconsistency and duplicated code.

**Solution:** Use middleware pipeline to handle cross-cutting concerns before requests reach handlers.

**Code Example:**
```python
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

class AuthMiddleware(Middleware):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def on_request(self, context: MiddlewareContext, call_next):
        # Extract API key from request
        provided_key = context.fastmcp_context.headers.get("X-API-Key")

        if provided_key != self.api_key:
            raise ToolError("Invalid API key")

        return await call_next(context)

class LoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        print(f"[{context.timestamp}] {context.method} from {context.source}")

        try:
            result = await call_next(context)
            print(f"[{context.timestamp}] {context.method} completed")
            return result
        except Exception as e:
            print(f"[{context.timestamp}] {context.method} failed: {e}")
            raise

# Apply middleware in order
mcp = FastMCP("Protected")
mcp.add_middleware(AuthMiddleware("secret-key"))  # First: auth
mcp.add_middleware(LoggingMiddleware())  # Second: logging
mcp.add_middleware(ResponseCachingMiddleware())  # Third: caching

# All tools now protected, logged, and cached
@mcp.tool
def get_data(query: str) -> dict:
    return {"result": f"Data for {query}"}
```

**Trade-offs:**
- ✅ **Advantages:** DRY principle, consistent behaviour, easy to add/remove concerns, testable in isolation
- ❌ **Disadvantages:** Middleware order matters (subtle bugs possible), performance overhead (multiple function calls), debugging can be harder (stack traces longer)
- 📊 **Complexity:** Medium

**When to Use:**
- Authentication/authorisation
- Request/response logging
- Performance timing
- Rate limiting
- Caching
- Error transformation
- Request validation

**When NOT to Use:**
- Tool-specific business logic
- When performance overhead of pipeline is prohibitive
- Simple servers with few tools (overkill)

**Related Patterns:** Chain of Responsibility, Decorator Pattern, Interceptor Pattern

**Real-World Examples:** All FastMCP built-in middleware, web framework middleware (Express.js, Django)

**Sources:** FastMCP Middleware Docs (Quality: A)
**Confidence:** HIGH

---

### Pattern 3: Server Composition for Modularity

**Intent:** Build large MCP applications from smaller, focused server modules

**Problem:** Monolithic servers become difficult to maintain as tools/resources grow. Teams working on different features conflict.

**Solution:** Create domain-specific servers and compose them using mounting or importing.

**Code Example:**
```python
from fastmcp import FastMCP

# Domain-specific servers
weather = FastMCP("Weather")

@weather.tool
def get_forecast(city: str) -> dict:
    return {"city": city, "temp": 22, "condition": "sunny"}

@weather.resource("weather://cities")
def list_cities() -> list[str]:
    return ["London", "Paris", "Tokyo"]

database = FastMCP("Database")

@database.tool
def query(sql: str) -> list[dict]:
    # Execute query
    return [{"id": 1, "name": "Alice"}]

@database.resource("db://stats")
def get_stats() -> dict:
    return {"queries_today": 1000}

# Compose into main server
main = FastMCP("Platform")

# Import: static copy (performance-critical)
await main.import_server(database, prefix="db")

# Mount: live link (dynamic updates needed)
main.mount(weather, prefix="weather")

# Result:
# Tools: db_query, weather_get_forecast
# Resources: db://stats, weather://cities

# Add platform-level tools
@main.tool
def health_check() -> dict:
    return {"status": "healthy", "uptime": "24h"}

main.run(transport="http", port=8000)
```

**Variant: Mounting Without Prefix** (useful for plugin architectures):
```python
plugins = FastMCP("Plugins")
main.mount(plugins)  # Tools appear with original names
```

**Trade-offs:**
- ✅ **Advantages:** Team autonomy, clear boundaries, independent testing, reusable modules, parallel development
- ❌ **Disadvantages:** Mounting adds latency, name collision risk without prefixes, complexity in debugging (multi-server traces)
- 📊 **Complexity:** Medium to High

**When to Use:**
- Large applications (10+ tools)
- Multi-team development
- Reusable utility servers (text processing, API integrations)
- Plugin architectures
- Gradual migration (mount legacy systems)

**When NOT to Use:**
- Small, simple servers (5-10 tools)
- Single-team projects with tight coupling
- Performance-critical paths (mounting overhead)

**Related Patterns:** Microservices, Plugin Architecture, Facade Pattern

**Real-World Examples:** FastMCP mount_example.py, enterprise platforms with domain-specific services

**Sources:** FastMCP Composition Docs, mount_example.py (Quality: A)
**Confidence:** HIGH

---

### Pattern 4: Environment Variable Configuration

**Intent:** Externalise configuration for different deployment environments

**Problem:** Hardcoding configuration (API keys, endpoints, timeouts) makes code inflexible and insecure.

**Solution:** Use environment variables for all configuration, with sensible defaults.

**Code Example:**
```python
import os
from fastmcp import FastMCP

# Configuration from environment
class Config:
    SERVER_NAME = os.getenv("MCP_SERVER_NAME", "DefaultServer")
    LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")
    API_ENDPOINT = os.getenv("API_ENDPOINT")  # Required, no default
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
    RATE_LIMIT = float(os.getenv("RATE_LIMIT", "10.0"))

    # Validate required config
    if not API_ENDPOINT:
        raise ValueError("API_ENDPOINT environment variable required")

mcp = FastMCP(
    name=Config.SERVER_NAME,
    middleware=[
        RateLimitingMiddleware(max_requests_per_second=Config.RATE_LIMIT),
        ResponseCachingMiddleware(list_tools_settings=ListToolsSettings(ttl=Config.CACHE_TTL))
    ]
)

@mcp.tool
async def fetch_data(query: str) -> dict:
    async with httpx.AsyncClient(timeout=Config.API_TIMEOUT) as client:
        response = await client.get(f"{Config.API_ENDPOINT}/data", params={"q": query})
        return response.json()
```

**Environment File Pattern** (.env):
```bash
# Development
MCP_SERVER_NAME="DevServer"
MCP_LOG_LEVEL="DEBUG"
API_ENDPOINT="http://localhost:8080"
API_TIMEOUT="60"
CACHE_TTL="60"
RATE_LIMIT="100.0"
```

```bash
# Production
MCP_SERVER_NAME="ProdServer"
MCP_LOG_LEVEL="WARNING"
API_ENDPOINT="https://api.production.com"
API_TIMEOUT="30"
CACHE_TTL="300"
RATE_LIMIT="10.0"
```

**Loading .env Files:**
```python
from dotenv import load_dotenv

load_dotenv()  # Loads .env file

# Or load different file for different environments
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)
```

**Trade-offs:**
- ✅ **Advantages:** Environment-specific config, no secrets in code, 12-factor app compliant, easy deployment variations
- ❌ **Disadvantages:** Environment variable sprawl, type safety issues (everything is string), no validation until runtime
- 📊 **Complexity:** Low

**When to Use:**
- Multi-environment deployments (dev/staging/prod)
- Docker/Kubernetes deployments
- Configuration that varies per deployment
- Sensitive data (API keys, credentials)

**When NOT to Use:**
- Configuration that's truly constant
- Complex nested configuration (use config files)
- Local development only

**Related Patterns:** 12-Factor App, Configuration as Code, Secret Management

**Real-World Examples:** All production MCP deployments, Docker Compose configurations

**Sources:** Dynamic Configuration Article, MCP Best Practices (Quality: B+)
**Confidence:** MEDIUM-HIGH

---

### Pattern 5: Context-Based State Sharing

**Intent:** Share authentication and request metadata between middleware and tools

**Problem:** Tools need information set by middleware (user ID, permissions, session data) but shouldn't couple directly to middleware.

**Solution:** Middleware sets state in Context; tools read state from Context.

**Code Example:**
```python
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

class AuthMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        # Extract user from token/headers
        token = context.fastmcp_context.headers.get("Authorization")
        user = self._validate_token(token)

        # Set state for tools to access
        if context.fastmcp_context:
            context.fastmcp_context.set_state("user_id", user["id"])
            context.fastmcp_context.set_state("user_role", user["role"])
            context.fastmcp_context.set_state("permissions", user["permissions"])

        return await call_next(context)

mcp = FastMCP("StateDemo")
mcp.add_middleware(AuthMiddleware())

@mcp.tool
async def get_user_profile(ctx: Context) -> dict:
    # Tools access state without coupling to middleware
    user_id = ctx.get_state("user_id")
    if not user_id:
        raise ToolError("Not authenticated")

    return {
        "user_id": user_id,
        "profile": fetch_profile(user_id)
    }

@mcp.tool
async def admin_operation(ctx: Context) -> str:
    # Role-based access using state
    role = ctx.get_state("user_role", default="user")
    if role != "admin":
        raise ToolError("Admin access required")

    return perform_admin_task()

@mcp.tool
async def check_permission(resource: str, ctx: Context) -> bool:
    # Fine-grained permissions
    permissions = ctx.get_state("permissions", default=[])
    return resource in permissions
```

**Trade-offs:**
- ✅ **Advantages:** Decouples middleware from tools, testable (mock state), flexible (easy to add new state), type-safe with defaults
- ❌ **Disadvantages:** State scoped to single request only (no cross-request persistence), requires Context parameter in tools, implicit contract between middleware and tools
- 📊 **Complexity:** Low to Medium

**When to Use:**
- User authentication/authorisation data
- Request tracing (request ID, correlation ID)
- Feature flags per request
- Rate limit buckets per user
- A/B test assignments

**When NOT to Use:**
- Data that must persist across requests (use database/cache)
- Large data objects (state is in-memory)
- When tools need to modify state that middleware reads (circular dependency)

**Related Patterns:** Context Pattern, Dependency Injection, Thread-Local Storage

**Real-World Examples:** Web framework request contexts (Flask's g, Django's request.user)

**Sources:** FastMCP Context Docs, Middleware Docs (Quality: A)
**Confidence:** HIGH

---

### Pattern 6: Graceful Error Handling with Middleware

**Intent:** Provide consistent, client-friendly error responses across all tools

**Problem:** Unhandled exceptions expose internal details, vary in format, and aren't logged consistently.

**Solution:** Error handling middleware catches exceptions, transforms them, logs them, and returns standardised responses.

**Code Example:**
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError, ResourceError
from mcp import McpError
from mcp.types import ErrorData
import logging

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(Middleware):
    def __init__(self, mask_errors: bool = False):
        self.mask_errors = mask_errors

    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)

        except (ToolError, ResourceError) as e:
            # Expected application errors
            logger.warning(f"{context.method} failed: {e}")
            raise  # Re-raise as-is

        except ValueError as e:
            # Validation errors
            logger.warning(f"Validation error in {context.method}: {e}")
            raise ToolError(f"Invalid input: {e}")

        except TimeoutError as e:
            # Timeout errors
            logger.error(f"Timeout in {context.method}: {e}")
            raise ToolError("Operation timed out, please try again")

        except Exception as e:
            # Unexpected errors
            logger.exception(f"Unexpected error in {context.method}: {e}")

            if self.mask_errors:
                # Production: mask internal details
                raise ToolError("An internal error occurred")
            else:
                # Development: show full error
                raise ToolError(f"Internal error: {type(e).__name__}: {e}")

# Configuration based on environment
mcp = FastMCP("ErrorDemo")
mcp.add_middleware(ErrorHandlingMiddleware(
    mask_errors=(os.getenv("ENV") == "production")
))

@mcp.tool
def divide(a: int, b: int) -> float:
    # Errors handled by middleware
    return a / b  # ZeroDivisionError caught and transformed
```

**Advanced: Error Recovery and Retry:**
```python
class ErrorRecoveryMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        max_retries = 3

        for attempt in range(max_retries):
            try:
                return await call_next(context)

            except TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise

            except Exception:
                # Don't retry other errors
                raise
```

**Trade-offs:**
- ✅ **Advantages:** Consistent error format, centralised logging, security (no info leakage), easier debugging (all errors logged)
- ❌ **Disadvantages:** May mask legitimate errors during development, harder to debug if middleware itself has bugs, performance cost of try/except
- 📊 **Complexity:** Medium

**When to Use:**
- Production deployments (security)
- APIs with multiple consumers (consistency)
- Logging/monitoring integration
- Error recovery and retry logic

**When NOT to Use:**
- Local development (want to see real errors)
- When tools need specific exception types from other tools

**Related Patterns:** Error Boundary (React), Exception Translation, Circuit Breaker

**Real-World Examples:** FastMCP ErrorHandlingMiddleware, web framework error handlers

**Sources:** FastMCP Middleware Docs, Production Security Articles (Quality: A/B+)
**Confidence:** HIGH

---

### Pattern 7: Resource Connection Pooling

**Intent:** Efficiently manage database connections and external API clients across multiple tool calls

**Problem:** Creating a new database connection or HTTP client for every tool call is slow and resource-intensive.

**Solution:** Create connection pools during server initialisation, reuse connections across calls, close on shutdown.

**Code Example:**
```python
from fastmcp import FastMCP
from contextlib import asynccontextmanager
import asyncpg
import httpx

@asynccontextmanager
async def lifespan(server: FastMCP):
    # Startup: create connection pools
    db_pool = await asyncpg.create_pool(
        host="localhost",
        port=5432,
        database="mydb",
        min_size=5,
        max_size=20,
        command_timeout=30,
    )

    http_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=100)
    )

    # Store in server settings for access by tools
    server.settings.db_pool = db_pool
    server.settings.http_client = http_client

    yield  # Server runs

    # Shutdown: close pools
    await db_pool.close()
    await http_client.aclose()

mcp = FastMCP("PoolDemo", lifespan=lifespan)

@mcp.tool
async def query_database(sql: str) -> list[dict]:
    # Access pool from server settings
    db_pool = mcp.settings.db_pool

    async with db_pool.acquire() as connection:
        rows = await connection.fetch(sql)
        return [dict(row) for row in rows]

@mcp.tool
async def fetch_api(url: str) -> dict:
    # Reuse HTTP client
    http_client = mcp.settings.http_client

    response = await http_client.get(url)
    response.raise_for_status()
    return response.json()
```

**Alternative: Context Manager Pattern:**
```python
from typing import AsyncIterator

class DatabaseConnection:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def __aenter__(self):
        self.connection = await self.pool.acquire()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pool.release(self.connection)

@mcp.tool
async def complex_query(query: str) -> list[dict]:
    async with DatabaseConnection(mcp.settings.db_pool) as conn:
        # Use connection
        result = await conn.fetch(query)
        return [dict(r) for r in result]
```

**Connection Pool Configuration:**
```python
# PostgreSQL pool settings
db_pool = await asyncpg.create_pool(
    dsn="postgresql://user:pass@localhost/db",
    min_size=5,          # Minimum connections maintained
    max_size=20,         # Maximum concurrent connections
    max_queries=50000,   # Recycle connection after N queries
    max_inactive_connection_lifetime=300,  # Close idle connections after 5min
    command_timeout=30,  # Query timeout
)

# HTTP client pool settings
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=100,      # Total connections
        max_keepalive_connections=20,  # Persistent connections
    ),
    http2=True,  # Enable HTTP/2 multiplexing
)
```

**Trade-offs:**
- ✅ **Advantages:** Significant performance improvement, lower resource usage, connection reuse, configurable limits prevent exhaustion
- ❌ **Disadvantages:** More complex initialisation, connection leaks if not properly released, tuning required (pool size, timeouts)
- 📊 **Complexity:** Medium

**When to Use:**
- Database access (always)
- External API calls (HTTP clients)
- Redis/cache connections
- Message queue connections
- Any I/O-bound operations

**When NOT to Use:**
- Single-use connections
- Extremely infrequent calls (pool overhead not worth it)

**Related Patterns:** Object Pool, Resource Acquisition Is Initialisation (RAII), Factory Pattern

**Real-World Examples:** FastMCP memory.py example, all production database applications

**Sources:** Connection Pooling Best Practices articles, memory.py example (Quality: B/A)
**Confidence:** MEDIUM-HIGH

---

### Pattern 8: Progressive Loading with Progress Reporting

**Intent:** Provide feedback during long-running operations

**Problem:** Long operations (large file processing, batch jobs) appear frozen to users without feedback.

**Solution:** Use Context.report_progress() to send progress updates to client.

**Code Example:**
```python
from fastmcp import FastMCP, Context

mcp = FastMCP("ProgressDemo")

@mcp.tool
async def process_large_dataset(file_uri: str, ctx: Context) -> dict:
    await ctx.info(f"Loading dataset from {file_uri}")

    # Load data
    data = await load_dataset(file_uri)
    total_items = len(data)

    await ctx.info(f"Processing {total_items} items")

    results = []
    for i, item in enumerate(data):
        # Process item
        result = await process_item(item)
        results.append(result)

        # Report progress every 10%
        if (i + 1) % (total_items // 10) == 0:
            await ctx.report_progress(
                progress=i + 1,
                total=total_items,
                status=f"Processed {i + 1}/{total_items} items"
            )

    await ctx.info("Processing complete")

    return {
        "processed": total_items,
        "results": results
    }
```

**Pattern: Nested Progress:**
```python
@mcp.tool
async def multi_stage_operation(ctx: Context) -> dict:
    stages = ["Download", "Extract", "Transform", "Load"]

    for stage_num, stage in enumerate(stages):
        await ctx.info(f"Stage {stage_num + 1}/{len(stages)}: {stage}")

        # Simulate stage work
        stage_items = 100
        for i in range(stage_items):
            await process_stage_item(stage, i)

            # Overall progress calculation
            overall_progress = (stage_num * 100 + i + 1) / len(stages)

            await ctx.report_progress(
                progress=int(overall_progress),
                total=100,
                status=f"{stage}: {i + 1}/{stage_items}"
            )

    return {"status": "complete"}
```

**Trade-offs:**
- ✅ **Advantages:** Better UX, operation visibility, allows cancellation decisions, helps identify bottlenecks
- ❌ **Disadvantages:** Network overhead (frequent updates), can slow operation slightly, client must support progress
- 📊 **Complexity:** Low

**When to Use:**
- File processing (large files)
- Batch operations
- Multi-step workflows
- Operations \u003e 5 seconds

**When NOT to Use:**
- Fast operations (\u003c 1 second)
- When progress can't be determined (unbounded loops)
- High-frequency updates would degrade performance

**Related Patterns:** Observer Pattern, Progress Bar, Async Iteration

**Real-World Examples:** FastMCP memory.py, file upload handlers

**Sources:** FastMCP Context Docs (Quality: A)
**Confidence:** HIGH

---

## Configuration Strategy

### Principles

1. **Environment-Based Configuration**: Different config for dev/staging/prod
2. **Sensible Defaults**: Work out-of-box for common cases
3. **Explicit Required Config**: Fail fast if required values missing
4. **No Secrets in Code**: Use environment variables or secret managers
5. **Immutable Configuration**: Set once at startup, don't change at runtime

### Configuration Layers

```mermaid
graph TB
    A[Application Defaults] --> B[Environment Variables]
    B --> C[Config Files]
    C --> D[Command-Line Arguments]
    D --> E[Final Configuration]

    style A fill:#E8F5E8
    style B fill:#E6F3FF
    style C fill:#F0E6FF
    style D fill:#FFF0E6
    style E fill:#F8D7DA
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class ServerConfig:
    # Server settings
    name: str = "MCPServer"
    version: str = "1.0.0"
    log_level: str = "INFO"

    # Transport settings
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000

    # Performance settings
    rate_limit: float = 10.0
    cache_ttl: int = 300
    connection_pool_size: int = 20
    request_timeout: int = 30

    # External services
    api_endpoint: Optional[str] = None
    database_url: Optional[str] = None
    redis_url: Optional[str] = None

    # Feature flags
    enable_caching: bool = True
    enable_auth: bool = False
    mask_errors: bool = False

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            name=os.getenv("MCP_SERVER_NAME", cls.name),
            version=os.getenv("MCP_VERSION", cls.version),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),

            transport=os.getenv("TRANSPORT", cls.transport),
            host=os.getenv("HOST", cls.host),
            port=int(os.getenv("PORT", cls.port)),

            rate_limit=float(os.getenv("RATE_LIMIT", cls.rate_limit)),
            cache_ttl=int(os.getenv("CACHE_TTL", cls.cache_ttl)),
            connection_pool_size=int(os.getenv("POOL_SIZE", cls.connection_pool_size)),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", cls.request_timeout)),

            api_endpoint=os.getenv("API_ENDPOINT"),
            database_url=os.getenv("DATABASE_URL"),
            redis_url=os.getenv("REDIS_URL"),

            enable_caching=os.getenv("ENABLE_CACHING", "true").lower() == "true",
            enable_auth=os.getenv("ENABLE_AUTH", "false").lower() == "true",
            mask_errors=os.getenv("MASK_ERRORS", "false").lower() == "true",
        )

    def validate(self):
        """Validate configuration and raise if invalid."""
        errors = []

        if self.transport == "http" and not (1024 <= self.port <= 65535):
            errors.append(f"Invalid port: {self.port}")

        if self.rate_limit <= 0:
            errors.append(f"Rate limit must be positive: {self.rate_limit}")

        # Check required config based on features
        if self.enable_auth and not os.getenv("AUTH_SECRET"):
            errors.append("AUTH_SECRET required when enable_auth=true")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Usage
config = ServerConfig.from_env()
config.validate()

mcp = FastMCP(
    name=config.name,
    version=config.version,
    middleware=[
        ErrorHandlingMiddleware(mask_errors=config.mask_errors),
        RateLimitingMiddleware(max_requests_per_second=config.rate_limit),
    ] + ([ResponseCachingMiddleware()] if config.enable_caching else [])
)
```

**Source:** Multiple configuration articles (Quality: B+), Confidence: MEDIUM-HIGH

---

## Error Handling

### Error Hierarchy

```mermaid
graph TB
    Exception["Exception"]
    FastMCPError["FastMCPError<br>base for all FastMCP errors"]
    ValidationError["ValidationError<br>parameter/return value validation"]
    ResourceError["ResourceError<br>resource operations"]
    ToolError["ToolError<br>tool operations"]
    PromptError["PromptError<br>prompt operations"]
    InvalidSignature["InvalidSignature<br>decorator usage errors"]
    ClientError["ClientError<br>client operations"]
    NotFoundError["NotFoundError<br>object not found"]
    DisabledError["DisabledError<br>object disabled"]
    McpError["McpError<br>MCP protocol errors"]

    Exception --> FastMCPError
    Exception --> McpError
    FastMCPError --> ValidationError
    FastMCPError --> ResourceError
    FastMCPError --> ToolError
    FastMCPError --> PromptError
    FastMCPError --> InvalidSignature
    FastMCPError --> ClientError
    FastMCPError --> NotFoundError
    FastMCPError --> DisabledError

    classDef error fill:#F8D7DA,stroke:#E74C3C,color:#000
    classDef base fill:#FFF0E6,stroke:#E67E22,color:#000

    class Exception base
    class FastMCPError,McpError error
    class ValidationError,ResourceError,ToolError,PromptError,InvalidSignature,ClientError,NotFoundError,DisabledError error
```

### Error Handling Strategy

**Layers of Error Handling:**

1. **Tool/Resource Level**: Raise appropriate FastMCP exceptions
2. **Middleware Level**: Transform, log, mask errors
3. **Protocol Level**: Convert to MCP error format
4. **Client Level**: Present errors to user

**Implementation:**

```python
from fastmcp.exceptions import ToolError, ValidationError
from mcp import McpError
from mcp.types import ErrorData

# Tool-level error handling
@mcp.tool
async def divide(a: int, b: int) -> float:
    if b == 0:
        raise ToolError("Division by zero not allowed")

    if not isinstance(a, int) or not isinstance(b, int):
        raise ValidationError("Parameters must be integers")

    return a / b

# Middleware-level error handling
class ErrorMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)

        except ToolError as e:
            # Log application errors
            logger.warning(f"Tool error: {e}")
            raise

        except ValidationError as e:
            # Transform validation errors
            logger.warning(f"Validation error: {e}")
            raise ToolError(f"Invalid input: {e}")

        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception(f"Unexpected error: {e}")

            if self.mask_errors:
                raise ToolError("An internal error occurred")
            raise ToolError(f"Internal error: {type(e).__name__}")
```

### Error Response Format

Errors are converted to MCP protocol format:

```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "error": {
    "code": -32000,
    "message": "Division by zero not allowed",
    "data": {
      "type": "ToolError",
      "details": "..."
    }
  }
}
```

**Source:** FastMCP exceptions.py, Middleware Docs (Quality: A), Confidence: HIGH

---

## Testing Strategy

### Testing Pyramid for MCP Servers

```mermaid
graph TB
    A[End-to-End Tests<br/>Full client-server integration<br/>10%]
    B[Integration Tests<br/>Multiple components<br/>20%]
    C[Unit Tests<br/>Individual tools/resources<br/>70%]

    A --> B
    B --> C

    style A fill:#F8D7DA
    style B fill:#FFF0E6
    style C fill:#E8F5E8
```

### Unit Testing Pattern

```python
import pytest
from fastmcp import FastMCP, Client

mcp = FastMCP("TestServer")

@mcp.tool
def add(a: int, b: int) -> int:
    return a + b

@mcp.tool
def divide(a: int, b: int) -> float:
    if b == 0:
        raise ToolError("Division by zero")
    return a / b

# Pytest fixture for in-memory testing
@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c

# Test successful operation
async def test_add(client: Client):
    result = await client.call_tool("add", {"a": 5, "b": 3})
    assert result.data == 8

# Test error handling
async def test_divide_by_zero(client: Client):
    with pytest.raises(ToolError, match="Division by zero"):
        await client.call_tool("divide", {"a": 10, "b": 0})

# Parametrised testing
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-5, 5, 0),
    (100, 200, 300),
])
async def test_add_parametrised(client: Client, a, b, expected):
    result = await client.call_tool("add", {"a": a, "b": b})
    assert result.data == expected
```

### Snapshot Testing Pattern

```python
from inline_snapshot import snapshot

async def test_tool_list(client: Client):
    tools = await client.list_tools()

    # First run: creates snapshot
    # Subsequent runs: compares to snapshot
    assert tools == snapshot([
        {
            "name": "add",
            "description": "Add two numbers",
            "inputSchema": {...}
        },
        {
            "name": "divide",
            "description": "Divide two numbers",
            "inputSchema": {...}
        }
    ])
```

Run with: `pytest --inline-snapshot=fix,create`

### Testing Middleware

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class CountingMiddleware(Middleware):
    def __init__(self):
        self.call_count = 0

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        self.call_count += 1
        return await call_next(context)

async def test_middleware():
    mcp = FastMCP("Test")
    middleware = CountingMiddleware()
    mcp.add_middleware(middleware)

    @mcp.tool
    def dummy() -> str:
        return "ok"

    async with Client(mcp) as client:
        await client.call_tool("dummy")
        await client.call_tool("dummy")

        assert middleware.call_count == 2
```

### Mocking External Dependencies

```python
from unittest.mock import AsyncMock, patch

@mcp.tool
async def fetch_weather(city: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.weather.com/{city}")
        return response.json()

async def test_fetch_weather(client: Client):
    mock_response = AsyncMock()
    mock_response.json.return_value = {"temp": 22, "condition": "sunny"}

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await client.call_tool("fetch_weather", {"city": "London"})

        assert result.data == {"temp": 22, "condition": "sunny"}
```

### Integration Testing with Docker

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  mcp-server:
    build: .
    environment:
      - DATABASE_URL=postgresql://test:test@postgres:5432/testdb
    depends_on:
      - postgres

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test
      - POSTGRES_DB=testdb
```

```python
# Test with real dependencies
@pytest.mark.integration
async def test_with_real_database():
    # Use Docker Compose environment
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("query_database", {"sql": "SELECT 1"})
        assert result.data == [{"?column?": 1}]
```

**Source:** FastMCP Testing Docs, MCPCat Testing Guide (Quality: A/B+), Confidence: HIGH

---

## Security Model

### Security Layers

```mermaid
graph TB
    A[Transport Security<br/>HTTPS/TLS] --> B[Authentication<br/>OAuth/JWT/API Keys]
    B --> C[Authorisation<br/>Role/Permission Checks]
    C --> D[Input Validation<br/>Schema Validation]
    D --> E[Output Sanitisation<br/>Error Masking]
    E --> F[Audit Logging<br/>Security Events]

    classDef security fill:#F8D7DA,stroke:#E74C3C,color:#000
    class A,B,C,D,E,F security
```

### Authentication Patterns

**OAuth for Production:**
```python
from fastmcp.server.auth.providers.google import GoogleProvider

auth = GoogleProvider(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    base_url="https://mcp.example.com",
    allowed_domains=["example.com"]  # Organisation restriction
)

mcp = FastMCP("Secured", auth=auth)
```

**API Key for Service-to-Service:**
```python
from fastmcp.server.auth import StaticTokenVerifier

auth = StaticTokenVerifier(
    tokens={
        os.getenv("SERVICE_A_KEY"): {"service": "service-a", "role": "reader"},
        os.getenv("SERVICE_B_KEY"): {"service": "service-b", "role": "writer"},
    }
)
```

### Authorisation Middleware

```python
class RBACMiddleware(Middleware):
    ROLE_PERMISSIONS = {
        "admin": ["*"],
        "writer": ["read", "write"],
        "reader": ["read"],
    }

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        user = context.fastmcp_context.get_state("user")
        role = user.get("role", "reader")

        tool_name = context.message.name
        required_permission = self._get_tool_permission(tool_name)

        if not self._has_permission(role, required_permission):
            raise ToolError(f"Insufficient permissions for {tool_name}")

        return await call_next(context)

    def _has_permission(self, role: str, permission: str) -> bool:
        role_perms = self.ROLE_PERMISSIONS.get(role, [])
        return "*" in role_perms or permission in role_perms
```

### Input Validation

FastMCP automatically validates inputs against tool schemas. Additional validation:

```python
from pydantic import BaseModel, Field, validator

class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(ge=1, le=100)

    @validator("query")
    def sanitise_query(cls, v):
        # Remove potentially dangerous characters
        dangerous = ["--", ";", "/*", "*/", "xp_", "sp_"]
        for pattern in dangerous:
            if pattern in v.lower():
                raise ValueError(f"Query contains dangerous pattern: {pattern}")
        return v

@mcp.tool
def search(query: SearchQuery) -> list[dict]:
    # query is validated by Pydantic
    return perform_search(query.query, query.limit)
```

### Output Sanitisation

```python
class SanitiseMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        result = await call_next(context)

        # Remove sensitive fields from responses
        if hasattr(result, "content"):
            result = self._sanitise_content(result)

        return result

    def _sanitise_content(self, result):
        sensitive_keys = ["password", "token", "secret", "api_key"]

        if isinstance(result, dict):
            return {
                k: "[REDACTED]" if k.lower() in sensitive_keys else v
                for k, v in result.items()
            }
        return result
```

### Security Best Practices

| Practice                | Implementation                              | Why                   |
|-------------------------|---------------------------------------------|-----------------------|
| **HTTPS in Production** | Deploy behind reverse proxy with TLS        | Encrypt transport     |
| **Mask Errors**         | `ErrorHandlingMiddleware(mask_errors=True)` | Don't leak internals  |
| **Rate Limiting**       | `RateLimitingMiddleware` per client         | Prevent abuse         |
| **Input Validation**    | Pydantic schemas + custom validators        | Prevent injection     |
| **Least Privilege**     | Role-based access control                   | Limit damage          |
| **Audit Logging**       | Log auth events, access denials             | Security monitoring   |
| **Dependency Scanning** | Regular security updates                    | Patch vulnerabilities |
| **Secret Management**   | Environment variables, never code           | Protect credentials   |

**Source:** Security articles, FastMCP Auth Docs (Quality: A/B+), Confidence: MEDIUM-HIGH

---

## Performance Considerations

### Bottleneck Identification

Common performance bottlenecks in MCP servers:

| Bottleneck              | Symptoms           | Solutions                                       |
|-------------------------|--------------------|-------------------------------------------------|
| **Database Queries**    | High tool latency  | Connection pooling, query optimisation, caching |
| **External API Calls**  | Slow responses     | HTTP client pooling, parallel requests, caching |
| **Large Payloads**      | Network saturation | Compression, pagination, streaming              |
| **Synchronous I/O**     | Thread blocking    | Async/await, non-blocking libraries             |
| **Middleware Overhead** | All requests slow  | Minimise middleware, optimise hot paths         |
| **JSON Serialisation**  | CPU spikes         | Use orjson/ujson, reduce payload size           |

### Optimisation Patterns

**1. Connection Pooling** (covered in Pattern 7)

**2. Response Caching:**
```python
from fastmcp.server.middleware.caching import ResponseCachingMiddleware, CallToolSettings

mcp.add_middleware(ResponseCachingMiddleware(
    call_tool_settings=CallToolSettings(
        ttl=300,  # Cache for 5 minutes
        included_tools=["expensive_query", "external_api"],
    )
))
```

**3. Async Parallel Execution:**
```python
import asyncio

@mcp.tool
async def fetch_multiple_sources(sources: list[str]) -> dict:
    # Fetch all sources in parallel
    results = await asyncio.gather(*[
        fetch_source(source) for source in sources
    ])

    return {"sources": dict(zip(sources, results))}
```

**4. Lazy Loading:**
```python
@mcp.resource("data://large-dataset")
async def get_large_dataset() -> str:
    # Don't load entire dataset, return reference
    return json.dumps({
        "url": "https://storage.example.com/dataset.parquet",
        "size": "10GB",
        "format": "parquet"
    })
```

**5. Pagination:**
```python
@mcp.tool
def list_items(page: int = 1, page_size: int = 50) -> dict:
    if page_size > 100:
        page_size = 100  # Max page size

    offset = (page - 1) * page_size
    items = query_items(limit=page_size, offset=offset)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": len(items) == page_size
    }
```

### Performance Monitoring

**Timing Middleware:**
```python
from fastmcp.server.middleware.timing import DetailedTimingMiddleware

mcp.add_middleware(DetailedTimingMiddleware())
```

**Custom Metrics:**
```python
from prometheus_client import Counter, Histogram

TOOL_CALLS = Counter("mcp_tool_calls_total", "Total tool calls", ["tool_name"])
TOOL_DURATION = Histogram("mcp_tool_duration_seconds", "Tool execution time", ["tool_name"])

class MetricsMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name

        TOOL_CALLS.labels(tool_name=tool_name).inc()

        with TOOL_DURATION.labels(tool_name=tool_name).time():
            return await call_next(context)
```

**Source:** General performance patterns, FastMCP Middleware (Quality: B/A), Confidence: MEDIUM

---

## Deployment Model

### Transport Selection

| Transport             | Use Case                     | Pros                | Cons                     |
|-----------------------|------------------------------|---------------------|--------------------------|
| **STDIO**             | Local CLI tools, development | Simple, no network  | Single client only       |
| **HTTP (Streamable)** | Production web deployment    | Stateless, scalable | More complex             |
| **HTTP Streaming**    | Cloud deployment             | Server push         | Production-ready         |

### Deployment Patterns

#### 1. Local Development (STDIO)

```python
if __name__ == "__main__":
    mcp.run()  # Defaults to STDIO
```

```bash
# Run directly
python server.py

# Via FastMCP CLI
fastmcp run server.py
fastmcp dev server.py  # Auto-reload
```

#### 2. Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose HTTP port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
```

**server.py:**
```python
if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",  # Accept external connections
        port=8000,
        path="/mcp"
    )
```

**Build and run:**
```bash
docker build -t mcp-server .
docker run -p 8000:8000 -e DATABASE_URL="..." mcp-server
```

#### 3. Kubernetes Deployment

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: mcp-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mcp-secrets
              key: database-url
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-server
spec:
  selector:
    app: mcp-server
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

#### 4. Managed Deployment (FastMCP Cloud)

```python
# Deploy to FastMCP Cloud - zero config
if __name__ == "__main__":
    # Automatic HTTPS, auth, monitoring
    mcp.run()  # CLI deployment via fastmcp cloud
```

### Health Checks

```python
@mcp.tool
def health_check() -> dict:
    return {
        "status": "healthy",
        "version": mcp.version,
        "uptime": get_uptime(),
        "dependencies": {
            "database": check_database(),
            "redis": check_redis(),
        }
    }
```

**Source:** Deployment articles, K8s guides (Quality: B+/B), Confidence: MEDIUM-HIGH

---

## Migration Path

### Evolving Base Components Without Breaking Consumers

Strategies for maintaining backwards compatibility:

#### 1. Semantic Versioning

```python
mcp = FastMCP(
    name="BaseComponents",
    version="2.1.0"  # MAJOR.MINOR.PATCH
)

# MAJOR: Breaking changes
# MINOR: New features, backwards compatible
# PATCH: Bug fixes, backwards compatible
```

#### 2. Deprecation Warnings

```python
import warnings

@mcp.tool
def old_tool(param: str) -> str:
    warnings.warn(
        "old_tool is deprecated, use new_tool instead",
        DeprecationWarning,
        stacklevel=2
    )
    return new_tool(param)

@mcp.tool
def new_tool(param: str) -> str:
    return f"New: {param}"
```

#### 3. Versioned Endpoints

```python
@mcp.tool
def process_data_v1(data: str) -> dict:
    """Version 1: simple processing."""
    return {"result": data.upper()}

@mcp.tool
def process_data_v2(data: str, options: dict) -> dict:
    """Version 2: with options."""
    return {"result": data.upper(), "options": options}

# Default to latest version
@mcp.tool
def process_data(data: str, options: dict | None = None) -> dict:
    """Current version delegates to v2."""
    return process_data_v2(data, options or {})
```

#### 4. Feature Flags

```python
@mcp.tool
def experimental_feature(ctx: Context) -> str:
    if not os.getenv("ENABLE_EXPERIMENTAL"):
        raise ToolError("Feature not enabled")

    return "Experimental result"
```

#### 5. Adapter Pattern for Breaking Changes

```python
# Old interface
class OldInterface:
    def process(self, data: str) -> str:
        return data.upper()

# New interface (breaking change)
class NewInterface:
    def process(self, data: dict) -> dict:
        return {"result": data["value"].upper()}

# Adapter maintains backwards compatibility
class CompatibilityAdapter:
    def __init__(self, new_impl: NewInterface):
        self.impl = new_impl

    def process(self, data: str | dict) -> str | dict:
        if isinstance(data, str):
            # Old interface - convert to new format
            result = self.impl.process({"value": data})
            return result["result"]
        else:
            # New interface - direct pass-through
            return self.impl.process(data)
```

### Migration Strategy

**Phase 1: Announce deprecation**
- Add deprecation warnings
- Update documentation
- Provide migration guide

**Phase 2: Parallel support**
- Run old and new implementations side-by-side
- Monitor usage of deprecated features
- Assist teams in migration

**Phase 3: Breaking change**
- Remove deprecated features in new MAJOR version
- Maintain old MAJOR version for security patches only

**Source:** API evolution articles, versioning guides (Quality: B), Confidence: MEDIUM

---

## Comparison Matrices

### Abstraction Layer Strategies

| Approach                                | Flexibility                     | Developer Experience                 | Performance                    | Maintenance                     | Best For                                 | Confidence |
|-----------------------------------------|---------------------------------|--------------------------------------|--------------------------------|---------------------------------|------------------------------------------|------------|
| **Thin Wrapper (minimal abstraction)**  | High - teams control everything | Low - must handle protocol details   | High - minimal overhead        | Low - duplicated patterns       | Experienced teams, custom requirements   | H          |
| **Middleware-Based (FastMCP approach)** | High - composable concerns      | High - declarative, minimal code     | Medium - pipeline overhead     | High - centralised patterns     | General purpose, mixed team experience   | H          |
| **Framework-Heavy (opinionated)**       | Low - constrained by framework  | High - convention over configuration | Medium - framework overhead    | High - well-documented patterns | Rapid development, standardisation       | M          |
| **Plugin Architecture**                 | High - extensible at runtime    | Medium - plugin API learning curve   | Low - dynamic loading overhead | Medium - plugin compatibility   | Evolving requirements, marketplace model | M          |

**Recommendation:** Middleware-Based approach (FastMCP pattern) - proven balance of flexibility and developer experience.

**Sources:** Multiple sources, architectural analysis
**Confidence Level Legend:** H = High, M = Medium, L = Low

---

### Configuration Pattern Approaches

| Pattern | Simplicity | Flexibility | Type Safety | Best For | Confidence |
|---------|-----------|-------------|-------------|----------|------------|
| **Environment Variables** | High | Medium | Low (all strings) | Container deployments, secrets | H |
| **Config Files (YAML/JSON)** | Medium | High | Low | Complex nested config | M |
| **Python Dataclasses** | Medium | High | High | Type-checked config | H |
| **Pydantic Models** | Low | High | High | Validated, complex config | H |
| **CLI Arguments** | High | Low | Medium | Simple overrides | M |

**Recommendation:** Python Dataclasses + Environment Variables - type safety with deployment flexibility.

---

### Error Handling Strategies

| Strategy                      | Robustness | Developer Experience       | Debugging                 | Performance        | Confidence |
|-------------------------------|------------|----------------------------|---------------------------|--------------------|------------|
| **No Error Handling**         | Low        | Poor (raw exceptions)      | Easy (stack traces)       | High (no overhead) | H          |
| **Try-Catch Everywhere**      | Medium     | Poor (boilerplate)         | Hard (lost context)       | Medium             | H          |
| **Middleware Error Handling** | High       | Excellent (automatic)      | Medium (middleware stack) | Medium (pipeline)  | H          |
| **Error Boundary Pattern**    | High       | Excellent (declarative)    | Easy (clear boundaries)   | Medium             | M          |
| **Result Type (Rust-style)**  | High       | Medium (explicit handling) | Easy (explicit errors)    | High               | L          |

**Recommendation:** Middleware Error Handling - consistent, automatic, production-ready.

---

### Testing Approaches

| Approach                         | Coverage           | Speed     | Maintenance        | Isolation      | Confidence |
|----------------------------------|--------------------|-----------|--------------------|----------------|------------|
| **In-Memory (FastMCPTransport)** | High (unit)        | Very Fast | Low                | Complete       | H          |
| **Docker Integration Tests**     | High (integration) | Slow      | Medium             | Good           | H          |
| **Mock External Dependencies**   | Medium             | Fast      | High (mocks break) | Complete       | H          |
| **Contract Testing**             | Medium             | Fast      | Medium             | Interface only | M          |
| **End-to-End (real clients)**    | Complete           | Very Slow | High               | None           | M          |

**Recommendation:** Combination: 70% In-Memory, 20% Docker Integration, 10% E2E.

---

### Deployment Patterns

| Pattern                 | Complexity | Scalability              | Isolation | Best For                      | Confidence |
|-------------------------|------------|--------------------------|-----------|-------------------------------|------------|
| **Local STDIO**         | Very Low   | None                     | Process   | Development, CLI tools        | H          |
| **Docker Container**    | Low        | Medium (single instance) | Good      | Simple deployments            | H          |
| **Kubernetes**          | High       | High (horizontal)        | Excellent | Production, high availability | H          |
| **Serverless (Lambda)** | Medium     | Auto-scaling             | Excellent | Event-driven, low traffic     | M          |
| **FastMCP Cloud**       | Very Low   | Auto-scaling             | Good      | Quick production, prototypes  | H          |

**Recommendation:** Docker for initial production, Kubernetes for scale, FastMCP Cloud for rapid deployment.

---

*End of Technical Architecture Document*

**Next Steps:**
1. Review patterns catalogue with team
2. Prototype key patterns (middleware, composition)
3. Create base component library implementing these patterns
4. Establish testing harness and CI/CD
5. Document migration guides for teams

**Questions for Client:**
- Scaling requirements (concurrent users, requests/second)?
- Deployment target (cloud provider, on-premise, hybrid)?
- Security compliance requirements (SOC2, HIPAA, etc.)?
- Team structure (how many teams, experience levels)?
- Timeline for rollout?
