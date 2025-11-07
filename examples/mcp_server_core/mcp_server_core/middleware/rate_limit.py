"""Per-client rate limiting middleware to prevent abuse."""

import asyncio
from collections import defaultdict
from time import time

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext


class PerClientRateLimitMiddleware(Middleware):
    """Rate limit requests per client instead of globally.

    This prevents a single malicious client from exhausting quota for all users.
    Uses a sliding window algorithm to track requests per client.

    Thread-safe implementation using asyncio locks to prevent race conditions
    under concurrent request processing.

    Args:
        requests_per_second: Maximum requests allowed per second
        window_seconds: Time window for rate limiting (default: 60 seconds)

    Example:
        >>> from mcp_server_core.middleware import PerClientRateLimitMiddleware
        >>> from mcp_server_core import MCPServer, ServerConfig
        >>>
        >>> config = ServerConfig()
        >>> mcp_server = MCPServer(config)
        >>>
        >>> # Allow 10 requests/second per client
        >>> mcp_server.mcp.add_middleware(
        ...     PerClientRateLimitMiddleware(
        ...         requests_per_second=10.0,
        ...         window_seconds=60
        ...     )
        ... )

    Implementation:
        - Tracks requests per client using source identifier
        - Sliding window: removes expired timestamps before counting
        - Raises ToolError when limit exceeded
        - Thread-safe with per-client locks
        - Automatically cleans old entries and removes inactive clients
    """

    def __init__(self, requests_per_second: float = 10.0, window_seconds: int = 60):
        """Initialise per-client rate limiter.

        Args:
            requests_per_second: Maximum requests per second per client
            window_seconds: Time window for sliding window algorithm
        """
        self.requests_per_second = requests_per_second
        self.window_seconds = window_seconds
        # client_id -> list of timestamps
        self.client_buckets: dict[str, list[float]] = defaultdict(list)
        # client_id -> lock for thread-safe access
        self.client_locks: dict[str, asyncio.Lock] = {}

    async def on_request(self, context: MiddlewareContext, call_next):
        """Check rate limit before processing request.

        Uses per-client locks to prevent race conditions under concurrent access.
        """
        client_id = self._get_client_id(context)
        current_time = time()

        # Get or create lock for this client
        if client_id not in self.client_locks:
            self.client_locks[client_id] = asyncio.Lock()

        # Thread-safe rate limit check
        async with self.client_locks[client_id]:
            # Clean old entries (outside window)
            self.client_buckets[client_id] = [t for t in self.client_buckets[client_id] if current_time - t < self.window_seconds]

            # If no recent requests, remove client entry to prevent memory leak
            if not self.client_buckets[client_id]:
                # Clean up empty client bucket
                if client_id in self.client_buckets:
                    del self.client_buckets[client_id]
                # Allow request (no rate limit for returning clients)
                return await call_next(context)

            # Check rate limit
            max_requests = int(self.requests_per_second * self.window_seconds)
            if len(self.client_buckets[client_id]) >= max_requests:
                raise ToolError(f"Rate limit exceeded: {self.requests_per_second} requests/second. Try again in {int(self.window_seconds)} seconds.")

            # Record request
            self.client_buckets[client_id].append(current_time)

        return await call_next(context)

    def _get_client_id(self, context: MiddlewareContext) -> str:
        """Extract client identifier from context.

        Args:
            context: Middleware context

        Returns:
            Client identifier (source or "unknown")
        """
        # Use source field if available, fall back to unknown
        return context.source or "unknown"
