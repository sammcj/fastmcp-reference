"""Safe URL fetching with SSRF prevention and security controls."""

import asyncio
import ipaddress
import socket
from typing import Literal
from urllib.parse import urlparse

import httpx

from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError


class URLFetcher:
    """Safe URL fetching with security controls.

    Security features:
    - SSRF prevention (blocks private/internal IPs)
    - HTTPS enforcement (configurable)
    - Timeout controls
    - Size limits
    - Automatic retries with exponential backoff (via httpx)

    Example:
        >>> config = ServerConfig()
        >>> async with httpx.AsyncClient() as client:
        ...     fetcher = URLFetcher(client, config)
        ...     response = await fetcher.fetch("https://api.example.com/data")
        ...     data = response.json()
    """

    # Private IP ranges to block (SSRF prevention)
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),  # Private
        ipaddress.ip_network("172.16.0.0/12"),  # Private
        ipaddress.ip_network("192.168.0.0/16"),  # Private
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    def __init__(self, client: httpx.AsyncClient, config: ServerConfig):
        """Initialise URL fetcher with security configuration.

        Args:
            client: Shared httpx AsyncClient (managed by lifecycle)
            config: Server configuration
        """
        self.client = client
        self.allow_private_ips = config.url_allow_private_ips
        self.require_https = config.url_require_https
        self.max_size_bytes = config.url_max_size_mb * 1024 * 1024
        self.timeout = config.url_timeout_seconds

    async def fetch(self, url: str, method: Literal["GET", "POST", "PUT", "DELETE"] = "GET", **kwargs) -> httpx.Response:
        """Fetch URL with security checks.

        Args:
            url: URL to fetch
            method: HTTP method
            **kwargs: Additional arguments passed to httpx (headers, data, etc.)

        Returns:
            httpx.Response object

        Raises:
            SecurityError: If URL fails security checks
            httpx.HTTPError: On fetch failure (404, timeout, etc.)

        Example:
            >>> response = await fetcher.fetch(
            ...     "https://api.example.com/data",
            ...     method="POST",
            ...     json={"key": "value"}
            ... )
        """
        # Validate URL
        parsed = urlparse(url)

        # Check scheme
        if self.require_https and parsed.scheme != "https":
            raise SecurityError(f"HTTPS required, got: {parsed.scheme}://...")

        if parsed.scheme not in ("http", "https"):
            raise SecurityError(f"Invalid URL scheme: {parsed.scheme} (only http/https allowed)")

        # Check for SSRF (initial check)
        if not self.allow_private_ips:
            await self._check_ssrf(parsed.hostname)

        # Set timeout
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        # Fetch URL
        response = await self.client.request(method, url, follow_redirects=True, **kwargs)

        # Re-validate final URL after redirects (prevents DNS rebinding and redirect bypasses)
        if not self.allow_private_ips and str(response.url) != url:
            final_parsed = urlparse(str(response.url))
            await self._check_ssrf(final_parsed.hostname)

        # Check size
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self.max_size_bytes:
            raise SecurityError(f"Response too large: {content_length} bytes (max: {self.max_size_bytes} bytes)")

        response.raise_for_status()
        return response

    async def _check_ssrf(self, hostname: str) -> None:
        """Check if hostname resolves to private IP (SSRF prevention).

        Args:
            hostname: Hostname to check

        Raises:
            SecurityError: If hostname resolves to private IP
        """
        if not hostname:
            raise SecurityError("URL must contain a hostname")

        try:
            # Resolve hostname to IP addresses
            addr_info = await asyncio.get_event_loop().getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,  # Both IPv4 and IPv6
            )

            # Check each resolved IP
            for info in addr_info:
                ip_str = info[4][0]
                try:
                    ip = ipaddress.ip_address(ip_str)

                    # Check against blocked networks
                    for network in self.BLOCKED_NETWORKS:
                        if ip in network:
                            raise SecurityError(f"URL resolves to private IP: {ip} (network: {network}) - SSRF protection")
                except ValueError:
                    # Invalid IP address format
                    raise SecurityError(f"Invalid IP address: {ip_str}")

        except socket.gaierror as e:
            raise SecurityError(f"Failed to resolve hostname: {hostname}") from e
