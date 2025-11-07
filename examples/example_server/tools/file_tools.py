"""Example tools using FileOperations for safe file access."""

from fastmcp import Context

from mcp_server_core.abstractions import FileOperations
from mcp_server_core.exceptions import SecurityError

__all__ = ["FileTools"]


class FileTools:
    """Tools for file operations with path traversal protection.

    Demonstrates:
    - Safe file reading/writing with directory restrictions
    - Automatic permission setting (0600 by default)
    - Path traversal prevention
    - Size limits
    """

    def __init__(self, file_ops: FileOperations):
        """Initialise with FileOperations instance."""
        self.file_ops = file_ops

    async def read_file(self, file_path: str, ctx: Context) -> dict:
        """Read file contents with security checks.

        Security features:
        - Directory whitelist enforcement
        - Path traversal prevention
        - Size limits

        Args:
            file_path: Path to file (must be in allowed directories)
            ctx: MCP context for logging

        Returns:
            {
                "path": str,
                "content": str,
                "size": int
            }

        Example:
            >>> result = await read_file("/tmp/data.txt")
        """
        await ctx.info(f"Reading file: {file_path}")

        try:
            content_bytes = await self.file_ops.read_file(file_path)
            content = content_bytes.decode("utf-8")

            await ctx.info(f"Successfully read file: {file_path}", extra={"size": len(content_bytes)})

            return {"path": file_path, "content": content, "size": len(content_bytes)}

        except SecurityError as e:
            await ctx.error(f"Security check failed for {file_path}", extra={"reason": str(e)})
            raise
        except FileNotFoundError as e:
            await ctx.error(f"File not found: {file_path}", extra={"error": str(e)})
            raise
        except UnicodeDecodeError as e:
            await ctx.error(f"File is not valid UTF-8: {file_path}", extra={"error": str(e)})
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error reading file: {file_path}", extra={"error": str(e), "type": type(e).__name__})
            raise

    async def write_file(self, file_path: str, content: str, ctx: Context) -> dict:
        """Write file with safe permissions.

        Security features:
        - Directory whitelist enforcement
        - Path traversal prevention
        - Automatic permission setting (0600 - owner read/write only)
        - Size limits

        Args:
            file_path: Path to write to (must be in allowed directories)
            content: Content to write
            ctx: MCP context for logging

        Returns:
            {
                "path": str,
                "bytes_written": int,
                "permissions": str
            }

        Example:
            >>> result = await write_file("/tmp/output.txt", "Hello, World!")
        """
        await ctx.info(f"Writing file: {file_path}")

        try:
            content_bytes = content.encode("utf-8")
            await self.file_ops.write_file(file_path, content_bytes)

            await ctx.info(f"Successfully wrote file: {file_path}", extra={"bytes": len(content_bytes)})

            return {"path": file_path, "bytes_written": len(content_bytes), "permissions": "0600 (owner read/write only)"}

        except SecurityError as e:
            await ctx.error(f"Security check failed for {file_path}", extra={"reason": str(e)})
            raise
        except PermissionError as e:
            await ctx.error(f"Permission denied writing to {file_path}", extra={"error": str(e)})
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error writing file: {file_path}", extra={"error": str(e), "type": type(e).__name__})
            raise

    async def list_directory(self, dir_path: str, ctx: Context) -> dict:
        """List files in directory.

        Security features:
        - Directory whitelist enforcement
        - Path traversal prevention

        Args:
            dir_path: Path to directory (must be in allowed directories)
            ctx: MCP context for logging

        Returns:
            {
                "path": str,
                "files": list[str],
                "count": int
            }

        Example:
            >>> result = await list_directory("/tmp")
        """
        await ctx.info(f"Listing directory: {dir_path}")

        try:
            files = await self.file_ops.list_directory(dir_path)

            await ctx.info(f"Successfully listed directory: {dir_path}", extra={"file_count": len(files)})

            return {"path": dir_path, "files": sorted(files), "count": len(files)}

        except SecurityError as e:
            await ctx.error(f"Security check failed for {dir_path}", extra={"reason": str(e)})
            raise
        except FileNotFoundError as e:
            await ctx.error(f"Directory not found: {dir_path}", extra={"error": str(e)})
            raise
        except PermissionError as e:
            await ctx.error(f"Permission denied accessing {dir_path}", extra={"error": str(e)})
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error listing directory: {dir_path}", extra={"error": str(e), "type": type(e).__name__})
            raise
