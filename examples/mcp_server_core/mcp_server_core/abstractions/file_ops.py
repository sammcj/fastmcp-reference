"""Safe file operations with path traversal protection and permission controls."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import aiofiles

from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError


class FileOperations:
    """Safe file operations with comprehensive security controls.

    Security features:
    - Path traversal prevention
    - Directory whitelist enforcement
    - Safe file permissions (default: 0600 - owner read/write only)
    - Size limits
    - Explicit allowed directories only

    Example:
        >>> config = ServerConfig()
        >>> file_ops = FileOperations(config)
        >>>
        >>> # Read file
        >>> content = await file_ops.read_file("/tmp/data.txt")
        >>>
        >>> # Write file with safe permissions
        >>> await file_ops.write_file("/tmp/output.txt", b"Hello, World!")
    """

    def __init__(self, config: ServerConfig):
        """Initialise file operations with security configuration.

        Args:
            config: Server configuration
        """
        self.allowed_dirs = [Path(d).resolve() for d in config.allowed_file_directories]
        self.max_size_bytes = config.max_file_size_mb * 1024 * 1024
        self.default_permissions = config.file_default_permissions

    def validate_path(self, file_path: str) -> Path:
        """Validate path is safe and within allowed directories.

        Args:
            file_path: File path to validate

        Returns:
            Resolved Path object

        Raises:
            SecurityError: If path is unsafe or outside allowed directories

        Example:
            >>> path = file_ops.validate_path("/tmp/data.txt")
            >>> assert path == Path("/tmp/data.txt")
        """
        # Resolve to absolute path (handles symlinks, .., etc.)
        try:
            path = Path(file_path).resolve(strict=False)
        except (ValueError, OSError) as e:
            raise SecurityError(f"Invalid file path: {file_path}") from e

        # Check for path traversal attempts in original string
        if ".." in file_path:
            raise SecurityError(f"Path traversal detected: {file_path} (contains '..')")

        # Check if path is within allowed directories
        is_allowed = False
        for allowed_dir in self.allowed_dirs:
            try:
                # Check if path is relative to allowed directory
                path.relative_to(allowed_dir)
                is_allowed = True
                break
            except ValueError:
                # Not relative to this allowed directory
                continue

        if not is_allowed:
            allowed_paths = ", ".join(str(d) for d in self.allowed_dirs)
            raise SecurityError(f"Path outside allowed directories: {path}\nAllowed directories: {allowed_paths}")

        return path

    async def read_file(self, file_path: str) -> bytes:
        """Read file with safety checks.

        Args:
            file_path: Path to file

        Returns:
            File contents as bytes

        Raises:
            SecurityError: If path is unsafe or file too large
            FileNotFoundError: If file doesn't exist

        Example:
            >>> content = await file_ops.read_file("/tmp/data.txt")
            >>> text = content.decode("utf-8")
        """
        path = self.validate_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise SecurityError(f"Path is not a file: {path}")

        # Re-validate after resolution (prevents TOCTOU symlink attacks)
        real_path = path.resolve(strict=True)
        if not any(real_path.is_relative_to(d) for d in self.allowed_dirs):
            raise SecurityError(f"Resolved path outside allowed: {real_path}")

        # Check size
        size = real_path.stat().st_size
        if size > self.max_size_bytes:
            raise SecurityError(f"File too large: {size} bytes (max: {self.max_size_bytes} bytes)")

        # For large files (> 1MB), use aiofiles to avoid blocking event loop
        if size > 1024 * 1024:
            async with aiofiles.open(real_path, "rb") as f:
                return await f.read()

        # Small files: use thread pool to avoid blocking event loop
        return await asyncio.to_thread(real_path.read_bytes)

    async def write_file(self, file_path: str, content: bytes, permissions: Optional[int] = None) -> None:
        """Write file with safe permissions.

        Args:
            file_path: Path to write to
            content: File contents as bytes
            permissions: Optional file permissions (octal, e.g., 0o600)
                        Defaults to config.file_default_permissions (0o600)

        Raises:
            SecurityError: If path is unsafe or content too large

        Example:
            >>> # Write with default permissions (0o600)
            >>> await file_ops.write_file("/tmp/output.txt", b"Hello")
            >>>
            >>> # Write with custom permissions
            >>> await file_ops.write_file("/tmp/public.txt", b"Hello", permissions=0o644)
        """
        path = self.validate_path(file_path)

        # Check size
        if len(content) > self.max_size_bytes:
            raise SecurityError(f"Content too large: {len(content)} bytes (max: {self.max_size_bytes} bytes)")

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # For large content (> 1MB), use aiofiles to avoid blocking event loop
        if len(content) > 1024 * 1024:
            async with aiofiles.open(path, "wb") as f:
                await f.write(content)
        else:
            # Small files: use thread pool to avoid blocking event loop
            await asyncio.to_thread(path.write_bytes, content)

        # Re-validate after write (prevents TOCTOU symlink attacks)
        real_path = path.resolve(strict=True)
        if not any(real_path.is_relative_to(d) for d in self.allowed_dirs):
            # Delete the file we just wrote since it's in wrong location
            path.unlink(missing_ok=True)
            raise SecurityError(f"Resolved path outside allowed: {real_path}")

        # Set permissions (default: 0600 - owner read/write only)
        perms = permissions if permissions is not None else self.default_permissions
        os.chmod(real_path, perms)

    async def delete_file(self, file_path: str) -> None:
        """Delete file with safety checks.

        Args:
            file_path: Path to file to delete

        Raises:
            SecurityError: If path is unsafe
            FileNotFoundError: If file doesn't exist

        Example:
            >>> await file_ops.delete_file("/tmp/temp.txt")
        """
        path = self.validate_path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise SecurityError(f"Path is not a file: {path}")

        path.unlink()

    async def list_directory(self, dir_path: str) -> list[str]:
        """List files in directory with safety checks.

        Args:
            dir_path: Path to directory

        Returns:
            List of file names (not full paths)

        Raises:
            SecurityError: If path is unsafe
            FileNotFoundError: If directory doesn't exist

        Example:
            >>> files = await file_ops.list_directory("/tmp")
            >>> print(files)  # ['data.txt', 'output.txt']
        """
        path = self.validate_path(dir_path)

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise SecurityError(f"Path is not a directory: {path}")

        # Return just file names, not full paths
        return [f.name for f in path.iterdir()]
