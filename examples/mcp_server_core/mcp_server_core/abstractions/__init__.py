"""Security-focused abstractions for common operations.

These abstractions prevent common vulnerabilities:
- URLFetcher: SSRF prevention, size limits
- FileOperations: Path traversal protection, safe permissions
- CodeExecutor: Sandboxed code execution (requires llm-sandbox)
"""

from mcp_server_core.abstractions.file_ops import FileOperations
from mcp_server_core.abstractions.url_fetcher import URLFetcher

__all__ = [
    "URLFetcher",
    "FileOperations",
]
