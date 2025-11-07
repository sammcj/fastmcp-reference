"""Example MCP server using mcp-server-core.

This server demonstrates:
- Using mcp-server-core for configuration and middleware
- Security abstractions (URLFetcher, FileOperations)
- Transport-aware logging (STDIO file-based, HTTP stdout)
- FastMCP built-in features (error handling, retry, rate limiting, timing)

Run with:
    python server.py  # Uses .env configuration
"""


from fastmcp import Context

from mcp_server_core import ServerConfig, MCPServer
from mcp_server_core.abstractions import URLFetcher, FileOperations
from tools.web_tools import WebTools
from tools.file_tools import FileTools


def main():
    """Main entry point for the server."""
    # Load configuration from environment
    config = ServerConfig()

    # Create MCP server with pre-configured middleware
    # HTTP client and config are available via ctx.app_context in tools
    mcp_server = MCPServer(config)

    # Register web tools
    @mcp_server.mcp.tool
    async def fetch_url(url: str, ctx: Context) -> dict:
        """Fetch content from a URL with security checks.

        Features:
        - SSRF prevention (blocks private IPs)
        - HTTPS requirement (in production)
        - Size and timeout limits

        Args:
            url: URL to fetch (e.g., "https://api.github.com")
            ctx: MCP context (provides http_client and config via app_context)

        Returns:
            URL metadata and content preview
        """
        # Access HTTP client and config from app_context (populated by lifespan handler)
        url_fetcher = URLFetcher(ctx.app_context["http_client"], ctx.app_context["config"])
        web_tools = WebTools(url_fetcher)
        return await web_tools.fetch_url(url, ctx)

    @mcp_server.mcp.tool
    async def fetch_json(url: str, ctx: Context) -> dict:
        """Fetch and parse JSON from a URL.

        Features:
        - SSRF prevention (blocks private IPs)
        - HTTPS requirement (in production)
        - Automatic JSON parsing

        Args:
            url: URL returning JSON (e.g., "https://api.github.com/users/octocat")
            ctx: MCP context (provides http_client and config via app_context)

        Returns:
            Parsed JSON data
        """
        url_fetcher = URLFetcher(ctx.app_context["http_client"], ctx.app_context["config"])
        web_tools = WebTools(url_fetcher)
        return await web_tools.fetch_json(url, ctx)

    # Register file tools
    @mcp_server.mcp.tool
    async def read_file(file_path: str, ctx: Context) -> dict:
        """Read file contents with security checks.

        Features:
        - Directory whitelist (only allowed directories)
        - Path traversal prevention
        - Size limits

        Args:
            file_path: Path to file (e.g., "/tmp/data.txt")
            ctx: MCP context (provides config via app_context)

        Returns:
            File contents and metadata
        """
        file_ops = FileOperations(ctx.app_context["config"])
        file_tools = FileTools(file_ops)
        return await file_tools.read_file(file_path, ctx)

    @mcp_server.mcp.tool
    async def write_file(file_path: str, content: str, ctx: Context) -> dict:
        """Write file with safe permissions.

        Features:
        - Directory whitelist (only allowed directories)
        - Path traversal prevention
        - Automatic safe permissions (0600)
        - Size limits

        Args:
            file_path: Path to write to (e.g., "/tmp/output.txt")
            content: Content to write
            ctx: MCP context (provides config via app_context)

        Returns:
            Write confirmation and metadata
        """
        file_ops = FileOperations(ctx.app_context["config"])
        file_tools = FileTools(file_ops)
        return await file_tools.write_file(file_path, content, ctx)

    @mcp_server.mcp.tool
    async def list_directory(dir_path: str, ctx: Context) -> dict:
        """List files in directory.

        Features:
        - Directory whitelist (only allowed directories)
        - Path traversal prevention

        Args:
            dir_path: Path to directory (e.g., "/tmp")
            ctx: MCP context (provides config via app_context)

        Returns:
            List of files in directory
        """
        file_ops = FileOperations(ctx.app_context["config"])
        file_tools = FileTools(file_ops)
        return await file_tools.list_directory(dir_path, ctx)

    # Register example tool demonstrating AI Precision Anti-Pattern avoidance
    @mcp_server.mcp.tool
    def calculate_total(items: list[dict], tax_rate: float = 0.10) -> dict:
        """Calculate order total using precise decimal arithmetic.

        This tool demonstrates the correct pattern:
        - LLM calls this tool with structured data
        - Tool performs precise calculations using Decimal
        - Never ask LLM to do maths

        Args:
            items: List of items with 'price' and 'quantity' keys
                  Example: [{"name": "Widget", "price": 10.50, "quantity": 2}]
            tax_rate: Tax rate as decimal (default: 0.10 for 10%)

        Returns:
            {
                "subtotal": float,
                "tax": float,
                "tax_rate": float,
                "total": float,
                "item_count": int
            }
        """
        from decimal import Decimal, ROUND_HALF_UP

        subtotal = Decimal("0.00")
        for item in items:
            price = Decimal(str(item["price"]))
            quantity = Decimal(str(item["quantity"]))
            subtotal += price * quantity

        # Apply tax rate
        tax_decimal = Decimal(str(tax_rate))
        tax = (subtotal * tax_decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + tax

        return {"subtotal": float(subtotal), "tax": float(tax), "tax_rate": tax_rate, "total": float(total), "item_count": len(items)}

    # Run server (blocks until shutdown)
    mcp_server.run()


if __name__ == "__main__":
    main()
