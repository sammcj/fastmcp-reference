# FastMCP Patterns & Anti-Patterns Catalogue

**Version:** 1.0
**Date:** 28 October 2025
**Purpose:** Reference guide for implementation patterns and anti-patterns

---

## Table of Contents

### Implementation Patterns
1. [Resource Template Pattern](#pattern-9-resource-template-pattern)
2. [Circuit Breaker Pattern](#pattern-10-circuit-breaker-pattern)
3. [Retry with Exponential Backoff](#pattern-11-retry-with-exponential-backoff)
4. [Tool Chaining Pattern](#pattern-12-tool-chaining-pattern)
5. [Streaming Progress Pattern](#pattern-13-streaming-progress-pattern)
6. [Tag-Based Tool Filtering](#pattern-14-tag-based-tool-filtering)
7. [Multi-Tenancy Pattern](#pattern-15-multi-tenancy-pattern)
8. [Graceful Degradation](#pattern-16-graceful-degradation)

### Anti-Patterns & Code Smells
1. [The AI Precision Anti-Pattern](#anti-pattern-1-the-ai-precision-anti-pattern) ⚠️ **CRITICAL**
2. [The Fat Tool](#anti-pattern-2-the-fat-tool)
3. [The God Server](#anti-pattern-3-the-god-server)
4. [Leaky Abstraction](#anti-pattern-4-leaky-abstraction)
5. [Middleware Soup](#anti-pattern-5-middleware-soup)
6. [State Leakage](#anti-pattern-6-state-leakage)
7. [Synchronous I/O in Async Context](#anti-pattern-7-synchronous-io-in-async-context)
8. [Missing Connection Cleanup](#anti-pattern-8-missing-connection-cleanup)
9. [Hardcoded Configuration](#anti-pattern-9-hardcoded-configuration)
10. [Silent Failures](#anti-pattern-10-silent-failures)
11. [Over-Abstraction](#anti-pattern-11-over-abstraction)
12. [Incomplete Error Handling](#anti-pattern-12-incomplete-error-handling)
13. [Testing in Production](#anti-pattern-13-testing-in-production)

---

## Additional Implementation Patterns

- **Do not use SSE Mode** - SSE mode has been deprecated in favour of streamable HTTP.
- **Do not EVER log to STDOUT/STDERR** - MCP uses STDOUT/STDERR for protocol communication. Use structured logging middleware instead.

### Pattern 9: Resource Template Pattern

**Intent:** Provide dynamic resources with parameterised URIs

**Problem:** Need to expose related resources without creating separate handlers for each variant.

**Solution:** Use URI templates with path parameters.

**Code Example:**
```python
from fastmcp import FastMCP

mcp = FastMCP("ResourceDemo")

# Static resource
@mcp.resource("users://list")
def list_users() -> list[dict]:
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# Dynamic resource template
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: int) -> dict:
    """Access via: users://123/profile"""
    user = fetch_user_by_id(user_id)
    return {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "created": user.created_at
    }

# Multi-parameter template
@mcp.resource("users://{user_id}/posts/{post_id}")
def get_user_post(user_id: int, post_id: int) -> dict:
    """Access via: users://123/posts/456"""
    post = fetch_post(user_id, post_id)
    return {
        "post_id": post_id,
        "user_id": user_id,
        "title": post.title,
        "content": post.content
    }

# Template with optional segments
@mcp.resource("data://{dataset}/summary")
def get_dataset_summary(dataset: str) -> str:
    """Access via: data://sales/summary"""
    stats = analyse_dataset(dataset)
    return f"Dataset: {dataset}\nRows: {stats.rows}\nColumns: {stats.columns}"
```

**Trade-offs:**
- ✅ **Advantages:** Scalable (infinite resources), RESTful design, type-safe parameters
- ❌ **Disadvantages:** Discovery harder (templates don't show all possible URIs), must validate parameters manually
- 📊 **Complexity:** Low

**When to Use:**
- User profiles, product pages, file paths
- RESTful resource hierarchies
- Large datasets with consistent structure

**When NOT to Use:**
- Small, fixed set of resources (use static resources)
- Complex query patterns (use tools with parameters)

**Sources:** FastMCP Resource Docs (Quality: A), Confidence: HIGH

---

### Pattern 10: Circuit Breaker Pattern

**Intent:** Prevent cascading failures when external services are down

**Problem:** When an external service fails, retry attempts consume resources and slow everything down.

**Solution:** After N failures, "open the circuit" and fail fast without attempting calls. Periodically test if service recovered.

**Code Example:**
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    timeout: int = 60  # Seconds before trying again
    success_threshold: int = 2  # Successes needed to close circuit

    def __post_init__(self):
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            # Check if timeout expired
            if datetime.now() - self.last_failure_time \u003e timedelta(seconds=self.timeout):
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise ToolError("Circuit breaker is OPEN - service unavailable")

        try:
            result = await func(*args, **kwargs)

            # Success path
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count \u003e= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count \u003e= self.failure_threshold:
                self.state = CircuitState.OPEN

            raise

# Usage in tool
weather_circuit = CircuitBreaker(failure_threshold=5, timeout=60)

@mcp.tool
async def get_weather(city: str) -> dict:
    async def fetch():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.weather.com/{city}", timeout=5.0)
            response.raise_for_status()
            return response.json()

    return await weather_circuit.call(fetch)
```

**Trade-offs:**
- ✅ **Advantages:** Prevents resource exhaustion, fast failure, automatic recovery testing
- ❌ **Disadvantages:** Additional complexity, must tune thresholds, can mask intermittent issues
- 📊 **Complexity:** Medium

**When to Use:**
- External API dependencies
- Database connections prone to failure
- Microservice calls
- Any unreliable external service

**When NOT to Use:**
- Internal function calls
- Services with SLAs guaranteeing uptime
- When immediate retry is acceptable

**Sources:** General resilience patterns (Quality: B), Confidence: MEDIUM

---

### Pattern 11: Retry with Exponential Backoff

**Intent:** Automatically retry failed operations with increasing delays

**Problem:** Transient failures (network blips, rate limits) should be retried, but aggressive retries make things worse.

**Solution:** Retry with exponentially increasing delays between attempts.

**Code Example:**
```python
import asyncio
from typing import TypeVar, Callable
import random

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> T:
    """
    Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential calculation (2 = double each time)
        jitter: Add random jitter to prevent thundering herd
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()

        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                raise  # Final attempt failed, re-raise

            # Calculate delay
            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            # Add jitter to prevent thundering herd problem
            if jitter:
                delay = delay * (0.5 + random.random())

            await asyncio.sleep(delay)

    # Should never reach here, but satisfy type checker
    raise last_exception

# Usage in tool
@mcp.tool
async def fetch_external_api(endpoint: str) -> dict:
    async def fetch():
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.example.com/{endpoint}")
            response.raise_for_status()
            return response.json()

    return await retry_with_backoff(
        fetch,
        max_retries=3,
        base_delay=1.0,
        jitter=True
    )

# Retry only specific exceptions
async def retry_on_rate_limit(func: Callable[[], T], max_retries: int = 5) -> T:
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limited
                if attempt == max_retries:
                    raise

                # Check Retry-After header
                retry_after = e.response.headers.get("Retry-After", "1")
                delay = float(retry_after)

                await asyncio.sleep(delay)
            else:
                raise  # Don't retry other HTTP errors
```

**Trade-offs:**
- ✅ **Advantages:** Handles transient failures automatically, respects rate limits, reduces load on failing services
- ❌ **Disadvantages:** Increases latency, can mask persistent problems, requires tuning
- 📊 **Complexity:** Low to Medium

**When to Use:**
- Network requests
- Rate-limited APIs
- Database connection attempts
- Any operation with transient failures

**When NOT to Use:**
- User input validation errors (won't fix with retry)
- Authorization failures (won't change)
- Resource not found (404) errors

**Sources:** General resilience patterns (Quality: B), Confidence: MEDIUM-HIGH

---

### Pattern 12: Tool Chaining Pattern

**Intent:** One tool calls other tools to compose functionality

**Problem:** Complex operations require multiple steps that could be reused individually.

**Solution:** Break into smaller tools, chain them together.

**Code Example:**
```python
from fastmcp import FastMCP, Context

mcp = FastMCP("ChainDemo")

# Atomic tools
@mcp.tool
async def fetch_user(user_id: int) -> dict:
    """Fetch user data."""
    return {"id": user_id, "name": "Alice", "email": "alice@example.com"}

@mcp.tool
async def fetch_user_posts(user_id: int) -> list[dict]:
    """Fetch user's posts."""
    return [
        {"id": 1, "title": "Post 1", "likes": 10},
        {"id": 2, "title": "Post 2", "likes": 25},
    ]

@mcp.tool
async def calculate_engagement(posts: list[dict]) -> dict:
    """Calculate engagement metrics."""
    total_likes = sum(p["likes"] for p in posts)
    avg_likes = total_likes / len(posts) if posts else 0

    return {
        "total_posts": len(posts),
        "total_likes": total_likes,
        "avg_likes_per_post": avg_likes
    }

# Composite tool chains atomic tools together
@mcp.tool
async def get_user_summary(user_id: int, ctx: Context) -> dict:
    """Get complete user summary (composite tool)."""
    await ctx.info(f"Fetching user {user_id} summary")

    # Chain tools using context
    user = await ctx.fastmcp.call_tool("fetch_user", {"user_id": user_id})
    posts = await ctx.fastmcp.call_tool("fetch_user_posts", {"user_id": user_id})
    engagement = await ctx.fastmcp.call_tool("calculate_engagement", {"posts": posts})

    return {
        "user": user,
        "posts": posts,
        "engagement": engagement
    }

# Alternative: Direct Python function calls (simpler, but less discoverable)
@mcp.tool
async def get_user_summary_v2(user_id: int) -> dict:
    """Get complete user summary (direct calls)."""
    user = await fetch_user(user_id)
    posts = await fetch_user_posts(user_id)
    engagement = await calculate_engagement(posts)

    return {
        "user": user,
        "posts": posts,
        "engagement": engagement
    }
```

**Trade-offs:**
- ✅ **Advantages:** Reusable atomic tools, composable operations, testable in isolation
- ❌ **Disadvantages:** More overhead (multiple tool calls), complexity in error handling, tight coupling between tools
- 📊 **Complexity:** Medium

**When to Use:**
- Multi-step workflows
- When atomic operations useful independently
- Building higher-level abstractions

**When NOT to Use:**
- Tight performance requirements
- Operations that don't decompose naturally
- Simple, single-purpose tools

**Sources:** FastMCP patterns, general composition patterns (Quality: B+), Confidence: MEDIUM

---

### Pattern 13: Streaming Progress Pattern

**Intent:** Provide real-time updates during long operations

**Problem:** Users need continuous feedback, not just start/end notifications.

**Solution:** Combine logging and progress reporting for detailed status updates.

**Code Example:**
```python
from fastmcp import FastMCP, Context
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class ProcessingStage:
    name: str
    total_items: int

mcp = FastMCP("StreamingDemo")

@mcp.tool
async def process_dataset(file_uri: str, ctx: Context) -> dict:
    """Process dataset with detailed progress reporting."""

    stages = [
        ProcessingStage("Download", 100),
        ProcessingStage("Parse", 500),
        ProcessingStage("Validate", 500),
        ProcessingStage("Transform", 500),
        ProcessingStage("Upload", 100),
    ]

    total_work = sum(stage.total_items for stage in stages)
    completed_work = 0

    results = {}

    for stage in stages:
        await ctx.info(f"Starting stage: {stage.name}")

        async for item_num in process_stage(stage):
            completed_work += 1

            # Report progress with detailed status
            await ctx.report_progress(
                progress=completed_work,
                total=total_work,
                status=f"{stage.name}: {item_num}/{stage.total_items}"
            )

            # Additional logging for significant events
            if item_num % 100 == 0:
                await ctx.info(f"{stage.name}: processed {item_num} items")

        results[stage.name] = stage.total_items

    await ctx.info("All stages complete")

    return {
        "status": "complete",
        "stages_completed": len(stages),
        "items_processed": total_work,
        "results": results
    }

async def process_stage(stage: ProcessingStage) -> AsyncIterator[int]:
    """Simulate processing stage items."""
    for i in range(1, stage.total_items + 1):
        # Simulate work
        await asyncio.sleep(0.01)
        yield i
```

**Advanced: Progress with ETAs:**
```python
from datetime import datetime, timedelta

@mcp.tool
async def process_with_eta(file_uri: str, ctx: Context) -> dict:
    total_items = 1000
    start_time = datetime.now()

    for i in range(1, total_items + 1):
        await process_item(i)

        # Calculate ETA
        elapsed = (datetime.now() - start_time).total_seconds()
        items_per_second = i / elapsed if elapsed \u003e 0 else 0
        remaining_items = total_items - i
        eta_seconds = remaining_items / items_per_second if items_per_second \u003e 0 else 0
        eta = datetime.now() + timedelta(seconds=eta_seconds)

        if i % 50 == 0:
            await ctx.report_progress(
                progress=i,
                total=total_items,
                status=f"Processed {i}/{total_items} - ETA: {eta.strftime('%H:%M:%S')}"
            )

    return {"processed": total_items}
```

**Trade-offs:**
- ✅ **Advantages:** Excellent UX, allows user cancellation decisions, debugging easier (see where it stuck)
- ❌ **Disadvantages:** Network overhead, slightly slower execution, requires client support
- 📊 **Complexity:** Low to Medium

**Sources:** FastMCP Context/Progress Docs (Quality: A), Confidence: HIGH

---

### Pattern 14: Tag-Based Tool Filtering

**Intent:** Organise and filter tools by tags for selective exposure

**Problem:** Some tools should only be available in certain contexts (admin, beta, premium).

**Solution:** Use tags to categorise tools, filter in middleware or during composition.

**Code Example:**
```python
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

mcp = FastMCP("TaggedServer")

# Define tools with tags
@mcp.tool(tags=["public", "read-only"])
def list_products() -> list[dict]:
    """Public endpoint."""
    return [{"id": 1, "name": "Product A"}]

@mcp.tool(tags=["public", "read-only"])
def get_product(product_id: int) -> dict:
    """Public endpoint."""
    return {"id": product_id, "name": "Product", "price": 99.99}

@mcp.tool(tags=["admin", "write"])
def create_product(name: str, price: float) -> dict:
    """Admin only."""
    return {"id": 123, "name": name, "price": price}

@mcp.tool(tags=["admin", "dangerous"])
def delete_product(product_id: int) -> bool:
    """Admin only, dangerous operation."""
    return True

@mcp.tool(tags=["beta", "experimental"])
def ai_recommendations() -> list[dict]:
    """Beta feature."""
    return [{"id": 1, "score": 0.95}]

# Middleware to enforce tag-based access
class TagFilterMiddleware(Middleware):
    def __init__(self, allowed_tags: set[str]):
        self.allowed_tags = allowed_tags

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        # Get all tools
        result = await call_next(context)

        # Filter tools by tags
        filtered_tools = [
            tool for tool in result
            if any(tag in self.allowed_tags for tag in tool.tags)
        ]

        return filtered_tools

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Check if tool is allowed
        if context.fastmcp_context:
            try:
                tool = await context.fastmcp_context.fastmcp.get_tool(
                    context.message.name
                )

                # Check if user has required tags
                if not any(tag in self.allowed_tags for tag in tool.tags):
                    raise ToolError(f"Access denied: insufficient permissions")

            except Exception:
                pass  # Tool not found or other error - let it fail naturally

        return await call_next(context)

# Configure based on user role
def create_user_server(user_role: str) -> FastMCP:
    allowed_tags = {
        "public": {"public", "read-only"},
        "user": {"public", "read-only", "beta"},
        "admin": {"public", "read-only", "admin", "write", "dangerous", "beta"},
    }

    user_server = FastMCP(f"Server-{user_role}")
    user_server.add_middleware(TagFilterMiddleware(allowed_tags[user_role]))

    # Import all tools
    user_server.import_server(mcp)

    return user_server

# Usage
public_server = create_user_server("public")  # Only public tools
admin_server = create_user_server("admin")    # All tools
```

**Server-Level Tag Filtering (FastMCP 2.8+):**
```python
# Declaratively filter at server creation
mcp = FastMCP(
    name="MyFilteredServer",
    # Only expose components with "public" tag
    include_tags={"public"},
    # Exclude any that are also tagged "beta"
    exclude_tags={"beta"}
)

@mcp.tool(tags={"public"})
def stable_feature():
    """This tool is public and will be exposed."""
    ...

@mcp.tool(tags={"public", "beta"})
def new_feature():
    """This tool is public but also beta, excluded."""
    ...
```

**Dynamic Enable/Disable (FastMCP 2.8+):**
```python
# Tools can be enabled/disabled at runtime
@mcp.tool(enabled=False)
def legacy_tool():
    """Disabled from the start."""
    ...

# Enable/disable programmatically
legacy_tool.enable()
legacy_tool.disable()
```

**Server Composition with Tag Filtering:**
```python
# Filter during composition
main = FastMCP("Main")

# Import only non-admin tools
await main.import_server(
    mcp,
    prefix="api",
    tag_filter=lambda tags: "admin" not in tags
)

# Mount with tag filtering
main.mount(
    admin_server,
    prefix="admin",
    tag_filter=lambda tags: "admin" in tags
)
```

**Trade-offs:**
- ✅ **Advantages:** Flexible access control, self-documenting (tags show purpose), composable (filter at multiple levels)
- ❌ **Disadvantages:** Enforcement requires middleware, tags are metadata only (not security boundary)
- 📊 **Complexity:** Low to Medium

**Sources:** FastMCP Middleware Docs, Composition Docs (Quality: A), Confidence: HIGH

---

### Pattern 15: Multi-Tenancy Pattern

**Intent:** Serve multiple tenants from single server with data isolation

**Problem:** Each customer/tenant needs isolated data and potentially different configurations.

**Solution:** Use middleware to extract tenant ID, store in Context, enforce at data layer.

**Code Example:**
```python
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

mcp = FastMCP("MultiTenantServer")

# Middleware to extract and validate tenant
class TenantMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        # Extract tenant ID from headers
        tenant_id = context.fastmcp_context.headers.get("X-Tenant-ID")

        if not tenant_id:
            raise ToolError("Missing X-Tenant-ID header")

        # Validate tenant exists and is active
        tenant = await validate_tenant(tenant_id)

        if not tenant.is_active:
            raise ToolError(f"Tenant {tenant_id} is inactive")

        # Store tenant context for tools
        if context.fastmcp_context:
            context.fastmcp_context.set_state("tenant_id", tenant_id)
            context.fastmcp_context.set_state("tenant", tenant)

        return await call_next(context)

mcp.add_middleware(TenantMiddleware())

# Tools automatically use tenant context
@mcp.tool
async def list_customers(ctx: Context) -> list[dict]:
    """List customers for current tenant."""
    tenant_id = ctx.get_state("tenant_id")

    # Query with tenant filter
    customers = await db.query(
        "SELECT * FROM customers WHERE tenant_id = $1",
        tenant_id
    )

    return [dict(c) for c in customers]

@mcp.tool
async def create_customer(name: str, email: str, ctx: Context) -> dict:
    """Create customer for current tenant."""
    tenant_id = ctx.get_state("tenant_id")

    # Insert with tenant association
    customer = await db.execute(
        "INSERT INTO customers (tenant_id, name, email) VALUES ($1, $2, $3) RETURNING *",
        tenant_id, name, email
    )

    return dict(customer)

@mcp.tool
async def get_tenant_stats(ctx: Context) -> dict:
    """Get statistics for current tenant."""
    tenant_id = ctx.get_state("tenant_id")
    tenant = ctx.get_state("tenant")

    customer_count = await db.fetchval(
        "SELECT COUNT(*) FROM customers WHERE tenant_id = $1",
        tenant_id
    )

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "customer_count": customer_count,
        "plan": tenant.plan
    }

# Database connection pooling per tenant
class TenantConnectionPool:
    def __init__(self):
        self.pools = {}

    async def get_pool(self, tenant_id: str):
        if tenant_id not in self.pools:
            tenant_config = await get_tenant_db_config(tenant_id)
            self.pools[tenant_id] = await asyncpg.create_pool(**tenant_config)

        return self.pools[tenant_id]

# Usage
tenant_pools = TenantConnectionPool()

@mcp.tool
async def query_data(sql: str, ctx: Context) -> list[dict]:
    tenant_id = ctx.get_state("tenant_id")

    # Get tenant-specific connection pool
    pool = await tenant_pools.get_pool(tenant_id)

    async with pool.acquire() as conn:
        # Add tenant filter to query automatically
        filtered_sql = add_tenant_filter(sql, tenant_id)
        rows = await conn.fetch(filtered_sql)

        return [dict(r) for r in rows]
```

**Trade-offs:**
- ✅ **Advantages:** Single deployment for all tenants, cost-efficient, centralized management
- ❌ **Disadvantages:** Noisy neighbour problem, security risk (tenant isolation must be perfect), scaling limits
- 📊 **Complexity:** High

**When to Use:**
- SaaS applications
- Platform services
- Controlled tenant environments

**When NOT to Use:**
- Strict data isolation requirements (use separate instances)
- Tenants with vastly different scale (largest dominates)
- Regulatory requirements for physical separation

**Sources:** General multi-tenancy patterns (Quality: B), Confidence: MEDIUM

---

### Pattern 16: Graceful Degradation

**Intent:** Continue operating with reduced functionality when dependencies fail

**Problem:** When optional services fail, entire application shouldn't fail.

**Solution:** Detect failures, provide fallback behaviour, inform user of degraded functionality.

**Code Example:**
```python
from fastmcp import FastMCP, Context
from dataclasses import dataclass
from typing import Optional

@dataclass
class ServiceHealth:
    cache: bool = True
    recommendations: bool = True
    analytics: bool = True

mcp = FastMCP("ResilientServer")

# Global health tracking
service_health = ServiceHealth()

@mcp.tool
async def get_products(category: str, ctx: Context) -> dict:
    """Get products with graceful degradation."""
    products = []

    # Primary operation - always required
    try:
        products = await fetch_products_from_db(category)
    except Exception as e:
        await ctx.error(f"Failed to fetch products: {e}")
        raise ToolError("Product service unavailable")

    # Optional: Try cache for performance
    if service_health.cache:
        try:
            cached_prices = await fetch_prices_from_cache(products)
            for product, price in zip(products, cached_prices):
                product["cached_price"] = price
        except Exception as e:
            await ctx.warning(f"Cache unavailable, using database prices: {e}")
            service_health.cache = False

    # Optional: Try recommendations
    if service_health.recommendations:
        try:
            recommendations = await fetch_recommendations(products)
            return {
                "products": products,
                "recommendations": recommendations,
                "features": ["cache", "recommendations"]
            }
        except Exception as e:
            await ctx.warning(f"Recommendations unavailable: {e}")
            service_health.recommendations = False

    # Optional: Try analytics
    if service_health.analytics:
        try:
            await record_search_analytics(category, products)
        except Exception as e:
            await ctx.warning(f"Analytics unavailable: {e}")
            service_health.analytics = False

    # Return with available features
    available_features = []
    if service_health.cache:
        available_features.append("cache")
    if service_health.recommendations:
        available_features.append("recommendations")
    if service_health.analytics:
        available_features.append("analytics")

    return {
        "products": products,
        "features": available_features,
        "degraded": not all([
            service_health.cache,
            service_health.recommendations,
            service_health.analytics
        ])
    }

# Health check tool
@mcp.tool
def health_status() -> dict:
    """Check service health and degraded features."""
    return {
        "status": "operational" if all([
            service_health.cache,
            service_health.recommendations,
            service_health.analytics
        ]) else "degraded",
        "services": {
            "cache": service_health.cache,
            "recommendations": service_health.recommendations,
            "analytics": service_health.analytics
        }
    }

# Periodic health recovery check
async def check_service_recovery():
    """Periodically test if degraded services recovered."""
    while True:
        await asyncio.sleep(60)  # Check every minute

        if not service_health.cache:
            try:
                await fetch_prices_from_cache([])
                service_health.cache = True
            except:
                pass

        if not service_health.recommendations:
            try:
                await fetch_recommendations([])
                service_health.recommendations = True
            except:
                pass

        if not service_health.analytics:
            try:
                await record_search_analytics("test", [])
                service_health.analytics = True
            except:
                pass
```

**Trade-offs:**
- ✅ **Advantages:** High availability, better UX (partial vs no functionality), automatic recovery
- ❌ **Disadvantages:** Complex error handling, must document degraded behaviour, users may not notice degradation
- 📊 **Complexity:** Medium to High

**Sources:** General resilience patterns (Quality: B), Confidence: MEDIUM

---

## Anti-Patterns & Code Smells

### Anti-Pattern 1: The AI Precision Anti-Pattern

⚠️ **SEVERITY: CRITICAL** - Undermines fundamental reliability of the system

**Description:** Using an LLM to perform deterministic tasks that require 100% accuracy and consistency, such as mathematical calculations, data format conversions, business rule execution, or precise data validation.

**Why It's Problematic:**

LLMs are probabilistic systems designed to generate plausible-sounding text, not verifiably correct results. Using an LLM for deterministic work introduces systemic unreliability:

- **Hallucinations:** The LLM confidently provides incorrect answers that appear well-structured but are factually wrong
- **Inconsistency:** The same query can yield different results on repeated calls due to probabilistic sampling
- **Unverifiable Results:** LLM "reasoning" cannot be formally audited or proven correct
- **Non-Repeatability:** Violates the core principle that deterministic operations must produce identical outputs for identical inputs

This is like asking a creative writer to file your taxes - you'll get a well-structured document, but it's unlikely to be numerically correct.

**How to Detect:**
- Prompts asking the LLM to "calculate," "convert," "validate," or "execute" precise operations
- Code parsing numerical or structured data directly from free-text LLM responses
- Lack of dedicated, deterministic tools for core business logic
- Test failures showing inconsistent results on identical inputs

**Code Smell Example:**
```python
# Anti-pattern: LLM doing deterministic calculations
@mcp.tool
async def calculate_order_total(items: list[dict], ctx: Context) -> float:
    """Calculate order total using LLM."""
    prompt = f"Calculate the total price for these items: {items}"
    # LLM doing maths - WRONG!
    response = await llm.complete(prompt)
    return float(response.content)  # Unreliable, inconsistent

# Anti-pattern: LLM doing data validation
@mcp.tool
async def validate_email(email: str, ctx: Context) -> bool:
    """Validate email format using LLM."""
    prompt = f"Is '{email}' a valid email address? Answer yes or no."
    response = await llm.complete(prompt)
    return "yes" in response.content.lower()  # Unreliable!
```

**Refactoring Approach:**

**Core Principle:** **LLMs orchestrate tools; tools execute logic.**

1. **Identify the Deterministic Task:** Isolate the precise operation (e.g., calculating cart total, validating email format)
2. **Create a Dedicated Tool:** Implement using standard, deterministic code with structured inputs/outputs
3. **Refactor the Agent Logic:** Have the LLM call the tool with required inputs rather than performing the calculation itself

```python
# Correct: Deterministic tool for calculations
@mcp.tool
def calculate_order_total(items: list[dict]) -> float:
    """Calculate order total using precise arithmetic."""
    total = sum(
        item["price"] * item["quantity"]
        for item in items
    )
    # Apply tax (deterministic calculation)
    tax_rate = 0.10
    return round(total * (1 + tax_rate), 2)

# Correct: Deterministic email validation
import re

@mcp.tool
def validate_email(email: str) -> dict:
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(pattern, email))
    return {
        "email": email,
        "is_valid": is_valid,
        "reason": "Valid format" if is_valid else "Invalid format"
    }

# LLM's role: Orchestration, not calculation
# The LLM now calls calculate_order_total() and validate_email()
# instead of trying to do the maths/validation itself
```

**Prevention:**
- **Architectural Review:** Ensure all precise, verifiable, or high-stakes operations are encapsulated in deterministic tools
- **Code Review Checklist:** Flag any code where LLM output is parsed for numerical or boolean values
- **Testing:** Deterministic operations must have unit tests proving identical inputs produce identical outputs
- **Documentation:** Make it clear that LLMs are for pattern recognition, not precision tasks

**Use LLMs For:**
- Text summarisation
- Pattern recognition
- Natural language interaction
- Content generation
- Brainstorming and ideation
- Orchestrating tool calls

**Never Use LLMs For:**
- Mathematical calculations
- Data format conversions
- Business rule execution
- Precise data validation
- Tasks requiring formal verification

**Related Patterns:** Tool Design, Error Handling

**Sources:**
- [The AI Precision Anti-Pattern - Scrum.org](https://www.scrum.org/resources/blog/ai-precision-anti-pattern)
- [Writing effective tools for AI agents - Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents)

**Confidence:** HIGH - Fundamental principle validated by multiple authoritative sources

---

### Anti-Pattern 2: The Fat Tool

**SEVERITY: HIGH** - Leads to unreliable LLM behaviour and technical debt

**Description:** A single MCP tool with multiple responsibilities, many optional parameters, or different modes of operation.

**Why It's Problematic:**
- **Cognitive Load for LLM:** Complex tools with many parameters are harder for LLMs to use correctly; models are more likely to hallucinate parameter combinations or misunderstand the tool's purpose
- **Poor Maintainability:** Large, multi-purpose functions violate the Single Responsibility Principle
- **Reduced Reusability:** A tool doing three things is less reusable than three focused tools

**How to Detect:**
- Tool function with more than 5 arguments
- Tool description containing "and," "or," or "depending on"
- Boolean flags that change core behaviour
- Multiple code paths based on parameter combinations

**Code Smell Example:**
```python
# Anti-pattern: Fat tool doing too much
@mcp.tool
def manage_user(
    action: str,  # "create", "update", "delete", "get"
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: Optional[str] = None,
    send_email: bool = False,
    dry_run: bool = False
) -> dict:
    """Manages users. Action can be create, update, delete, or get.
    Depending on action, different parameters are required."""
    if action == "create":
        # create logic
    elif action == "update":
        # update logic
    elif action == "delete":
        # delete logic
    elif action == "get":
        # get logic
    # Too complex, LLM will make mistakes!
```

**Refactoring Approach:**

Decompose into focused tools with clear, distinct purposes. Use nouns and verbs that align with API design best practices.

```python
# Correct: Focused tools with clear purposes
@mcp.tool
def create_user(email: str, name: str, role: str = "user") -> dict:
    """Create a new user account."""
    user = User(email=email, name=name, role=role)
    db.save(user)
    return {"id": user.id, "email": user.email, "name": user.name}

@mcp.tool
def get_user(user_id: int) -> dict:
    """Retrieve user information by ID."""
    user = db.get_user(user_id)
    if not user:
        raise ToolError(f"User {user_id} not found")
    return {"id": user.id, "email": user.email, "name": user.name}

@mcp.tool
def update_user_email(user_id: int, new_email: str) -> dict:
    """Update a user's email address."""
    user = db.get_user(user_id)
    if not user:
        raise ToolError(f"User {user_id} not found")
    user.email = new_email
    db.save(user)
    return {"id": user.id, "email": user.email}

@mcp.tool
def delete_user(user_id: int) -> dict:
    """Delete a user account."""
    user = db.get_user(user_id)
    if not user:
        raise ToolError(f"User {user_id} not found")
    db.delete(user)
    return {"id": user_id, "deleted": True}
```

**Prevention:**
- Follow Anthropic's guidance: "Build a few thoughtful tools targeting specific high-impact workflows"
- Each tool should do one thing and do it well
- Prefer multiple focused tools over one complex tool

**Sources:**
- [Writing effective tools for AI agents - Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents)

**Confidence:** HIGH

---

### Anti-Pattern 3: The God Server

**Description:** Single MCP server with 50+ tools covering unrelated domains.

**Why It's Problematic:**
- Difficult to maintain and test
- Team coordination nightmare
- Deployment risk (one bug breaks everything)
- Tight coupling between unrelated features
- Violates Single Responsibility Principle

**How to Detect:**
- More than 20-30 tools in single server
- Tools from completely different domains (weather + database + auth + ...)
- Multiple teams modifying same server
- Frequent merge conflicts

**Code Smell Example:**
```python
# Anti-pattern: Everything in one server
mcp = FastMCP("GodServer")

# Weather tools
@mcp.tool
def get_forecast(...): ...

@mcp.tool
def get_temperature(...): ...

# Database tools
@mcp.tool
def query_db(...): ...

@mcp.tool
def update_record(...): ...

# Auth tools
@mcp.tool
def login(...): ...

@mcp.tool
def logout(...): ...

# File operations
@mcp.tool
def read_file(...): ...

@mcp.tool
def write_file(...): ...

# API integrations
@mcp.tool
def call_stripe(...): ...

@mcp.tool
def call_sendgrid(...): ...

# And 40 more...
```

**Refactoring Approach:**
```python
# Pattern: Separate domain servers

# Weather server
weather = FastMCP("Weather")

@weather.tool
def get_forecast(...): ...

@weather.tool
def get_temperature(...): ...

# Database server
database = FastMCP("Database")

@database.tool
def query_db(...): ...

@database.tool
def update_record(...): ...

# Compose into main
main = FastMCP("Platform")
main.mount(weather, prefix="weather")
main.mount(database, prefix="db")
```

**Prevention:**
- Start with server composition from day 1
- Establish clear domain boundaries
- One server per team/service
- Review server size regularly

**Severity:** HIGH

**Sources:** Server Composition patterns, software architecture principles (Quality: B+), Confidence: HIGH

---

### Anti-Pattern 4: Leaky Abstraction

**SEVERITY: CRITICAL** - Negates platform value and introduces operational risk

**Description:** Tool implementations that bypass the platform's abstraction layer and interact directly with low-level resources (e.g., creating their own database connections instead of using provided connection pools, or directly instantiating HTTP clients instead of using shared clients).

**Why It's Problematic:**

This completely undermines the benefits of the platform:

- **Loses Platform Features:** Tool misses connection pooling, transaction management, standardised error handling, and observability
- **Resource Leaks:** Unmanaged connections lead to resource exhaustion
- **Inconsistent Behaviour:** Creates "shadow" infrastructure that's unmonitored and unreliable
- **Security Vulnerabilities:** Bypasses centralised security controls
- **Technical Debt:** Duplicates infrastructure logic across tools

**How to Detect:**
- Direct instantiation of resource clients in tool code (`create_engine()`, `httpx.Client()`, `psycopg2.connect()`)
- Missing logs or metrics for specific tools (suggests bypassing platform context)
- Tools managing their own connection lifecycle
- Code reviews spotting forbidden low-level library imports

**Code Smell Example:**
```python
# Anti-pattern: Bypassing platform abstractions
@mcp.tool
async def get_customer_data(customer_id: int) -> dict:
    """Get customer data - WRONG WAY."""
    # Creating own DB connection - bypasses platform pool!
    engine = create_async_engine("postgresql://...")  # BAD!
    async with engine.connect() as conn:
        result = await conn.execute(
            "SELECT * FROM customers WHERE id = $1",
            (customer_id,)
        )
        return dict(result.fetchone())
    # No cleanup, no transaction management, no observability!

# Anti-pattern: Direct HTTP client usage
@mcp.tool
async def call_external_api(endpoint: str) -> dict:
    """Call external API - WRONG WAY."""
    # Creating own HTTP client instead of using shared one
    async with httpx.AsyncClient() as client:  # BAD!
        response = await client.get(endpoint)
        return response.json()
    # No retry logic, no rate limiting, no metrics!
```

**Refactoring Approach:**

Use the platform's abstraction layer (base classes or shared resources):

```python
# Correct: Using platform's DatabaseTool abstraction
from platform_core.abstractions import DatabaseTool
from platform_core.server import mcp_server

class CustomerTool(DatabaseTool):
    @mcp_server.tool
    async def get_customer_data(self, customer_id: int, ctx: Context) -> dict:
        """Get customer data using platform abstractions."""
        return await self._execute_in_transaction(
            self._get_customer_impl, ctx, customer_id
        )

    async def _get_customer_impl(
        self, conn: AsyncConnection, ctx: Context, customer_id: int
    ) -> dict:
        # Connection provided by platform, managed automatically
        result = await conn.execute(
            "SELECT * FROM customers WHERE id = $1",
            (customer_id,)
        )
        row = result.fetchone()
        if not row:
            raise ToolError(f"Customer {customer_id} not found")
        return dict(row)

# Correct: Using platform's shared HTTP client
from platform_core.lifecycle import server_state

@mcp_server.tool
async def call_external_api(endpoint: str, ctx: Context) -> dict:
    """Call external API using shared client."""
    # Use shared, managed HTTP client from platform
    if not server_state.http_client:
        raise ToolError("HTTP client not initialized")

    response = await server_state.http_client.get(endpoint)
    response.raise_for_status()
    return response.json()
    # Platform handles connection pooling, retry logic, metrics!
```

**Prevention:**
- **Code Review Checklists:** Flag direct use of forbidden low-level libraries
- **Static Analysis:** Lint rules to detect `create_engine`, `httpx.Client()`, `psycopg2.connect()` in tool code
- **Documentation:** Clear examples showing correct usage of platform abstractions
- **Training:** Ensure developers understand the platform's abstraction layer

**Related Anti-Patterns:** Missing Connection Cleanup, Hardcoded Configuration

**Sources:**
- Connection pooling best practices
- Platform engineering patterns

**Confidence:** HIGH

---

### Anti-Pattern 5: Middleware Soup

**Description:** 10+ middleware stacked without clear purpose or ordering.

**Why It's Problematic:**
- Performance degradation (every request through 10+ layers)
- Debugging nightmare (which middleware caused issue?)
- Order-dependent bugs
- Unclear responsibility (multiple middleware doing similar things)

**How to Detect:**
- More than 5-6 middleware on single server
- Middleware with overlapping functionality
- Frequently changing middleware order to fix bugs
- Long stack traces through middleware

**Code Smell Example:**
```python
# Anti-pattern: Middleware soup
mcp = FastMCP("OverMiddlewared")
mcp.add_middleware(LoggingMiddleware())
mcp.add_middleware(AnotherLoggingMiddleware())  # Duplicate
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(PerformanceMiddleware())  # Overlaps with timing
mcp.add_middleware(AuthMiddleware())
mcp.add_middleware(PermissionMiddleware())  # Should be in auth
mcp.add_middleware(RateLimitMiddleware())
mcp.add_middleware(ThrottleMiddleware())  # Duplicate
mcp.add_middleware(CachingMiddleware())
mcp.add_middleware(CompressionMiddleware())
mcp.add_middleware(ErrorHandlingMiddleware())
mcp.add_middleware(ErrorTransformMiddleware())  # Overlaps
mcp.add_middleware(DebugMiddleware())
```

**Refactoring Approach:**
```python
# Pattern: Consolidated, purposeful middleware

# Combine related functionality
class SecurityMiddleware(Middleware):
    """Handles auth + permissions + rate limiting."""
    async def on_request(self, context, call_next):
        # Auth check
        user = await self.authenticate(context)

        # Permission check
        if not await self.authorize(user, context):
            raise ToolError("Insufficient permissions")

        # Rate limit check
        if not await self.check_rate_limit(user):
            raise ToolError("Rate limit exceeded")

        return await call_next(context)

# Minimal, focused middleware stack
mcp = FastMCP("CleanServer")
mcp.add_middleware(SecurityMiddleware())        # Auth + authz + rate limit
mcp.add_middleware(ObservabilityMiddleware())   # Logging + timing combined
mcp.add_middleware(ErrorHandlingMiddleware())   # Error transformation
mcp.add_middleware(ResponseCachingMiddleware()) # Caching
```

**Prevention:**
- Limit to 5-6 middleware maximum
- Combine related functionality
- Document purpose of each middleware
- Review middleware stack regularly

**Severity:** MEDIUM

---

### Anti-Pattern 6: State Leakage

**Description:** Sharing mutable state between requests via global variables or class attributes.

**Why It's Problematic:**
- Race conditions in concurrent requests
- Data leaks between users/tenants
- Unpredictable behaviour
- Security vulnerabilities

**How to Detect:**
- Global variables modified by tools
- Class attributes used for request state
- Requests affecting each other
- Race condition bugs

**Code Smell Example:**
```python
# Anti-pattern: Global state
current_user = None  # Shared across all requests!
processing_data = {}  # Shared!

@mcp.tool
def login(username: str, password: str) -> bool:
    global current_user

    if authenticate(username, password):
        current_user = username  # BUG: Concurrent requests clobber this
        return True
    return False

@mcp.tool
def get_my_data() -> dict:
    global current_user

    if not current_user:
        raise ToolError("Not logged in")

    # BUG: current_user might have changed since login!
    return fetch_data(current_user)

# Class attribute anti-pattern
class DataProcessor:
    current_operation = None  # Shared across instances!

    @mcp.tool
    def process(self, data: str) -> str:
        self.current_operation = data  # BUG: Race condition
        result = expensive_processing(self.current_operation)
        return result
```

**Refactoring Approach:**
```python
# Pattern: Use Context for request-scoped state

@mcp.tool
def login(username: str, password: str, ctx: Context) -> bool:
    if authenticate(username, password):
        # Store in request-scoped context
        ctx.set_state("user", username)
        return True
    return False

@mcp.tool
def get_my_data(ctx: Context) -> dict:
    # Read from context (request-scoped)
    user = ctx.get_state("user")

    if not user:
        raise ToolError("Not logged in")

    return fetch_data(user)

# For cross-request state, use external storage
@mcp.tool
async def start_long_operation(job_id: str, ctx: Context) -> str:
    # Store in database/cache, not memory
    await redis.set(f"job:{job_id}:status", "running")

    # Process...

    await redis.set(f"job:{job_id}:status", "complete")
    return job_id

@mcp.tool
async def get_job_status(job_id: str) -> str:
    # Read from external storage
    return await redis.get(f"job:{job_id}:status")
```

**Prevention:**
- Use Context for request-scoped state
- Use external storage (database, cache) for cross-request state
- Avoid global variables
- Use immutable data structures where possible

**Severity:** CRITICAL

---

### Anti-Pattern 7: Synchronous I/O in Async Context

**Description:** Blocking I/O calls in async functions, defeating concurrency.

**Why It's Problematic:**
- Blocks event loop, freezing entire server
- Defeats purpose of async/await
- Poor performance under load
- Can cause timeouts

**How to Detect:**
- `time.sleep()` in async functions
- Synchronous database libraries (psycopg2, not asyncpg)
- `requests` library instead of `httpx`
- File I/O without `aiofiles`

**Code Smell Example:**
```python
# Anti-pattern: Blocking calls
import time
import requests

@mcp.tool
async def fetch_data(url: str) -> dict:
    # BUG: Blocks event loop for 5 seconds!
    time.sleep(5)

    # BUG: Synchronous HTTP request blocks!
    response = requests.get(url)

    return response.json()

@mcp.tool
async def process_file(path: str) -> str:
    # BUG: Synchronous file I/O blocks!
    with open(path) as f:
        content = f.read()

    return content.upper()
```

**Refactoring Approach:**
```python
# Pattern: Async I/O
import asyncio
import httpx
import aiofiles

@mcp.tool
async def fetch_data(url: str) -> dict:
    # Async sleep doesn't block event loop
    await asyncio.sleep(5)

    # Async HTTP client
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    return response.json()

@mcp.tool
async def process_file(path: str) -> str:
    # Async file I/O
    async with aiofiles.open(path) as f:
        content = await f.read()

    return content.upper()

# CPU-bound work: use thread pool
import concurrent.futures

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

@mcp.tool
async def cpu_intensive(data: str) -> str:
    # Run CPU-intensive work in thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, expensive_computation, data)

    return result
```

**Prevention:**
- Use async libraries: `httpx` not `requests`, `asyncpg` not `psycopg2`, `aiofiles` not `open()`
- Use `asyncio.sleep()` not `time.sleep()`
- Run CPU-bound work in thread/process pools
- Lint with async-aware tools

**Severity:** HIGH

---

### Anti-Pattern 8: Missing Connection Cleanup

**Description:** Not closing database connections, HTTP clients, or file handles.

**Why It's Problematic:**
- Resource leaks (exhausted connections)
- File descriptor limits exceeded
- Memory leaks
- Eventually causes crashes

**How to Detect:**
- Increasing memory usage over time
- "Too many open files" errors
- Connection pool exhaustion errors
- Resource warnings on shutdown

**Code Smell Example:**
```python
# Anti-pattern: No cleanup
@mcp.tool
async def query_database(sql: str) -> list[dict]:
    # BUG: Connection never closed!
    conn = await asyncpg.connect("postgresql://...")

    rows = await conn.fetch(sql)

    return [dict(r) for r in rows]  # conn leaked!

@mcp.tool
async def fetch_api(url: str) -> dict:
    # BUG: Client never closed!
    client = httpx.AsyncClient()

    response = await client.get(url)

    return response.json()  # client leaked!
```

**Refactoring Approach:**
```python
# Pattern: Use context managers + connection pooling
from contextlib import asynccontextmanager

# Connection pool created at startup
@asynccontextmanager
async def lifespan(server: FastMCP):
    # Startup
    db_pool = await asyncpg.create_pool("postgresql://...")
    http_client = httpx.AsyncClient()

    server.settings.db_pool = db_pool
    server.settings.http_client = http_client

    yield

    # Shutdown: cleanup
    await db_pool.close()
    await http_client.aclose()

mcp = FastMCP("Server", lifespan=lifespan)

# Tools use pooled resources
@mcp.tool
async def query_database(sql: str) -> list[dict]:
    # Connection properly released
    async with mcp.settings.db_pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]

@mcp.tool
async def fetch_api(url: str) -> dict:
    # Reuse client, no cleanup needed
    response = await mcp.settings.http_client.get(url)
    return response.json()

# For one-off resources, use try/finally
@mcp.tool
async def process_temp_file(path: str) -> str:
    f = await aiofiles.open(path)
    try:
        content = await f.read()
        return content.upper()
    finally:
        await f.close()
```

**Prevention:**
- Always use context managers (`async with`)
- Create connection pools at startup
- Use lifespan hooks for cleanup
- Test resource cleanup in integration tests

**Severity:** CRITICAL

---

### Anti-Pattern 9: Hardcoded Configuration

**Description:** Hardcoding API keys, endpoints, timeouts in code.

**Why It's Problematic:**
- Security risk (credentials in source control)
- Inflexible (can't change without code changes)
- Different environments require code changes
- Difficult to manage secrets

**How to Detect:**
- Secrets visible in code
- Different branches for dev/prod
- Manual changes before deployment
- Credentials in git history

**Code Smell Example:**
```python
# Anti-pattern: Hardcoded
DATABASE_URL = "postgresql://admin:password123@localhost/prod"  # In code!
API_KEY = "sk-1234567890abcdef"  # Committed to git!
TIMEOUT = 30  # Can't change without deployment

@mcp.tool
async def fetch_data(query: str) -> dict:
    conn = await asyncpg.connect(DATABASE_URL)  # Hardcoded!

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            "https://api.example.com/data",
            headers={"Authorization": f"Bearer {API_KEY}"}  # Hardcoded!
        )

    return response.json()
```

**Refactoring Approach:**
```python
# Pattern: Environment variables + validation
import os
from dataclasses import dataclass

@dataclass
class Config:
    database_url: str
    api_key: str
    api_endpoint: str
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        # Required config
        database_url = os.getenv("DATABASE_URL")
        api_key = os.getenv("API_KEY")
        api_endpoint = os.getenv("API_ENDPOINT")

        if not all([database_url, api_key, api_endpoint]):
            raise ValueError("Missing required environment variables")

        # Optional config with defaults
        timeout = int(os.getenv("TIMEOUT", "30"))

        return cls(
            database_url=database_url,
            api_key=api_key,
            api_endpoint=api_endpoint,
            timeout=timeout
        )

# Load config at startup
config = Config.from_env()

# Use config in tools
@mcp.tool
async def fetch_data(query: str) -> dict:
    conn = await asyncpg.connect(config.database_url)

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await client.get(
            f"{config.api_endpoint}/data",
            headers={"Authorization": f"Bearer {config.api_key}"}
        )

    return response.json()
```

**Prevention:**
- Use environment variables for all config
- Use secret managers (AWS Secrets Manager, Vault) for production
- Validate config at startup
- Never commit secrets to git
- Use `.env` files for local development (git-ignored)

**Severity:** CRITICAL

---

### Anti-Pattern 10: Silent Failures

**Description:** Catching exceptions without logging or re-raising.

**Why It's Problematic:**
- Errors go unnoticed
- Debugging impossible (no logs)
- Users get incorrect results
- Masks underlying problems

**How to Detect:**
- Empty `except:` blocks
- Returning `None` on errors without logging
- Operations appearing to succeed but doing nothing

**Code Smell Example:**
```python
# Anti-pattern: Silent failures
@mcp.tool
async def save_data(data: dict) -> bool:
    try:
        await database.insert(data)
        return True
    except:
        # BUG: Error completely hidden!
        return False

@mcp.tool
async def fetch_optional_data(id: int) -> dict | None:
    try:
        return await database.get(id)
    except:
        # BUG: Can't tell if not found or database error
        return None
```

**Refactoring Approach:**
```python
# Pattern: Log errors, use specific exceptions
import logging

logger = logging.getLogger(__name__)

@mcp.tool
async def save_data(data: dict) -> bool:
    try:
        await database.insert(data)
        return True
    except asyncpg.UniqueViolationError as e:
        # Expected error - log and inform user
        logger.warning(f"Duplicate data: {e}")
        raise ToolError("Data already exists")
    except Exception as e:
        # Unexpected error - log with full context
        logger.exception(f"Failed to save data: {e}")
        raise ToolError("Failed to save data")

@mcp.tool
async def fetch_optional_data(id: int) -> dict | None:
    try:
        return await database.get(id)
    except database.NotFoundError:
        # Expected: not found is OK
        return None
    except Exception as e:
        # Unexpected: database error should be raised
        logger.exception(f"Database error fetching {id}: {e}")
        raise ToolError("Database error")
```

**Prevention:**
- Always log exceptions (at minimum)
- Use specific exception types
- Re-raise or convert to appropriate error
- Never use bare `except:`
- Use error handling middleware for consistency

**Severity:** HIGH

---

### Anti-Pattern 11: Over-Abstraction

**Description:** Too many abstraction layers making code hard to follow.

**Why It's Problematic:**
- Code navigation nightmare
- Difficult for new developers
- Performance overhead
- Premature optimisation

**How to Detect:**
- More than 3-4 layers of indirection to perform simple operations
- Abstract base classes with single implementation
- Factories creating factories
- Can't find where actual work happens

**Code Smell Example:**
```python
# Anti-pattern: Over-abstraction
class AbstractDataProvider(ABC):
    @abstractmethod
    async def provide_data(self): ...

class DataProviderFactory(ABC):
    @abstractmethod
    def create_provider(self): ...

class ConcreteDataProviderFactory(DataProviderFactory):
    def create_provider(self):
        return ConcreteDataProvider()

class ConcreteDataProvider(AbstractDataProvider):
    async def provide_data(self):
        return await self._fetch_from_source()

    async def _fetch_from_source(self):
        return await self._execute_query()

    async def _execute_query(self):
        # Finally, actual work!
        return [{"id": 1}]

# Usage: 6 layers of indirection!
@mcp.tool
async def get_data() -> list[dict]:
    factory = ConcreteDataProviderFactory()
    provider = factory.create_provider()
    return await provider.provide_data()
```

**Refactoring Approach:**
```python
# Pattern: Simple, direct code
@mcp.tool
async def get_data() -> list[dict]:
    # Direct, clear, easy to understand
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM data")
        return [dict(r) for r in rows]

# Abstraction only when actually needed
async def fetch_from_database(query: str) -> list[dict]:
    """Single abstraction layer if shared across tools."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]

@mcp.tool
async def get_users() -> list[dict]:
    return await fetch_from_database("SELECT * FROM users")

@mcp.tool
async def get_products() -> list[dict]:
    return await fetch_from_database("SELECT * FROM products")
```

**Prevention:**
- Follow YAGNI (You Aren't Gonna Need It)
- Add abstractions when pattern emerges, not preemptively
- Prefer composition over inheritance
- Keep it simple until complexity is justified

**Severity:** MEDIUM

---

### Anti-Pattern 12: Incomplete Error Handling

**Description:** Only handling happy path, ignoring error cases.

**Why It's Problematic:**
- Application crashes on errors
- Poor user experience
- Security vulnerabilities (error messages expose internals)

**How to Detect:**
- No try/except blocks
- No validation of inputs
- Assumes external services always available

**Code Smell Example:**
```python
# Anti-pattern: No error handling
@mcp.tool
async def divide(a: int, b: int) -> float:
    # BUG: No check for division by zero
    return a / b

@mcp.tool
async def fetch_user(user_id: int) -> dict:
    # BUG: Assumes user exists
    user = await database.get(user_id)
    return {
        "name": user.name,  # Crashes if user is None
        "email": user.email
    }

@mcp.tool
async def call_external_api(endpoint: str) -> dict:
    # BUG: No timeout, no error handling
    response = await httpx.get(f"https://api.example.com/{endpoint}")
    return response.json()  # Crashes on non-JSON response
```

**Refactoring Approach:**
```python
# Pattern: Comprehensive error handling
from fastmcp.exceptions import ToolError, ValidationError

@mcp.tool
async def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValidationError("Cannot divide by zero")

    return a / b

@mcp.tool
async def fetch_user(user_id: int) -> dict:
    if user_id \u003c= 0:
        raise ValidationError("User ID must be positive")

    user = await database.get(user_id)

    if not user:
        raise ToolError(f"User {user_id} not found")

    return {
        "name": user.name,
        "email": user.email
    }

@mcp.tool
async def call_external_api(endpoint: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.example.com/{endpoint}"
            )
            response.raise_for_status()

            return response.json()

    except httpx.TimeoutException:
        raise ToolError("API request timed out")
    except httpx.HTTPStatusError as e:
        raise ToolError(f"API returned error: {e.response.status_code}")
    except ValueError:
        raise ToolError("API returned invalid JSON")
```

**Prevention:**
- Think about failure modes
- Validate all inputs
- Handle expected errors explicitly
- Use error handling middleware
- Test error paths

**Severity:** HIGH

---

### Anti-Pattern 13: Testing in Production

**Description:** No testing infrastructure, discovering bugs in production.

**Why It's Problematic:**
- Users encounter bugs first
- No confidence in changes
- Difficult to reproduce issues
- Slow feedback loop

**How to Detect:**
- No test suite
- Manual testing only
- Frequent production hotfixes
- Fear of making changes

**Code Smell Example:**
```python
# Anti-pattern: No tests
# Just ship it and hope it works!

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
    # YOLO!
```

**Refactoring Approach:**
```python
# Pattern: Comprehensive test suite

# tests/test_tools.py
import pytest
from fastmcp import FastMCP, Client

# Test fixture
@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c

# Unit tests
async def test_divide(client: Client):
    result = await client.call_tool("divide", {"a": 10, "b": 2})
    assert result.data == 5.0

async def test_divide_by_zero(client: Client):
    with pytest.raises(ValidationError, match="Cannot divide by zero"):
        await client.call_tool("divide", {"a": 10, "b": 0})

# Integration tests
@pytest.mark.integration
async def test_with_real_database():
    # Use Docker Compose for test environment
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("fetch_user", {"user_id": 1})
        assert "name" in result.data

# CI/CD pipeline
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: pytest
      - run: pytest --cov=src
```

**Prevention:**
- Write tests from day 1
- Use in-memory testing for speed
- Set up CI/CD early
- Require tests for new features
- Test error paths, not just happy path

**Severity:** HIGH

---

## Summary

### Pattern Priorities

**Must-Have Patterns (Start Here):**
1. In-Memory Testing
2. Middleware for Cross-Cutting Concerns
3. Environment Variable Configuration
4. Context-Based State Sharing
5. Connection Pooling

**Add As You Scale:**
6. Server Composition
7. Circuit Breaker
8. Retry with Exponential Backoff
9. Tag-Based Filtering
10. Graceful Degradation

**Advanced (As Needed):**
11. Resource Templates
12. Tool Chaining
13. Streaming Progress
14. Multi-Tenancy

### Anti-Pattern Severity

**Critical (Fix Immediately):**
- State Leakage
- Missing Connection Cleanup
- Hardcoded Configuration

**High (Fix Soon):**
- God Server
- Synchronous I/O in Async Context
- Silent Failures
- Incomplete Error Handling
- Testing in Production

**Medium (Refactor When Possible):**
- Middleware Soup
- Over-Abstraction

---

*End of Patterns & Anti-Patterns Catalogue*
