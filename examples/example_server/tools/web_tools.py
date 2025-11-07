"""Example tools using URLFetcher for safe web requests."""

from fastmcp import Context
from httpx import HTTPError, TimeoutException

from mcp_server_core.abstractions import URLFetcher
from mcp_server_core.exceptions import SecurityError

__all__ = ["WebTools"]


class WebTools:
    """Tools for fetching web content with SSRF protection.

    Demonstrates:
    - Safe URL fetching with SSRF prevention
    - Automatic HTTPS enforcement (in production)
    - Size limits and timeouts
    - Error handling with Context logging
    """

    def __init__(self, url_fetcher: URLFetcher):
        """Initialize with URLFetcher instance."""
        self.fetcher = url_fetcher

    async def fetch_url(self, url: str, ctx: Context) -> dict:
        """Fetch content from a URL with security checks.

        Security features:
        - SSRF prevention (blocks private IPs)
        - HTTPS requirement (in production)
        - Size limits
        - Timeout controls

        Args:
            url: URL to fetch
            ctx: MCP context for logging

        Returns:
            {
                "url": str,
                "status_code": int,
                "content_type": str,
                "content_length": int,
                "content": str  # First 1000 chars
            }

        Example:
            >>> result = await fetch_url("https://api.github.com")
        """
        await ctx.info(f"Fetching URL: {url}")

        try:
            response = await self.fetcher.fetch(url, method="GET")

            content = response.text
            preview = content[:1000] + "..." if len(content) > 1000 else content

            await ctx.info(f"Successfully fetched {url}", extra={"status_code": response.status_code, "content_length": len(content)})

            return {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", "unknown"),
                "content_length": len(content),
                "content": preview,
            }

        except SecurityError as e:
            await ctx.error(f"Security check failed for {url}", extra={"reason": str(e)})
            raise
        except TimeoutException:
            await ctx.error(f"Timeout fetching {url}", extra={"timeout": self.fetcher.timeout})
            raise
        except HTTPError as e:
            await ctx.error(f"HTTP error fetching {url}", extra={"status": e.response.status_code if e.response else None, "error": str(e)})
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error fetching {url}", extra={"error": str(e), "type": type(e).__name__})
            raise

    async def fetch_json(self, url: str, ctx: Context) -> dict:
        """Fetch and parse JSON from a URL.

        Args:
            url: URL returning JSON
            ctx: MCP context for logging

        Returns:
            Parsed JSON data

        Example:
            >>> data = await fetch_json("https://api.github.com/users/octocat")
        """
        await ctx.info(f"Fetching JSON from: {url}")

        try:
            response = await self.fetcher.fetch(url, method="GET")
            data = response.json()

            await ctx.info(f"Successfully parsed JSON from {url}", extra={"keys": list(data.keys()) if isinstance(data, dict) else None})

            return data

        except SecurityError as e:
            await ctx.error(f"Security check failed for {url}", extra={"reason": str(e)})
            raise
        except TimeoutException:
            await ctx.error(f"Timeout fetching {url}", extra={"timeout": self.fetcher.timeout})
            raise
        except HTTPError as e:
            await ctx.error(f"HTTP error fetching {url}", extra={"status": e.response.status_code if e.response else None, "error": str(e)})
            raise
        except ValueError as e:
            await ctx.error(f"Invalid JSON response from {url}", extra={"error": str(e)})
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error fetching {url}", extra={"error": str(e), "type": type(e).__name__})
            raise
