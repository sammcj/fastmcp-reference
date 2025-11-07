"""Tests for FileOperations security abstraction."""

import tempfile
from pathlib import Path

import pytest

from mcp_server_core.abstractions import FileOperations
from mcp_server_core.config import ServerConfig
from mcp_server_core.exceptions import SecurityError


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def file_ops(temp_dir):
    """Create FileOperations with test config."""
    config = ServerConfig(server_name="test-server", environment="dev", allowed_file_directories=[temp_dir, "/tmp"])
    return FileOperations(config)


def test_validate_path_allowed(file_ops, temp_dir):
    """Test validating path within allowed directory."""
    test_file = Path(temp_dir) / "test.txt"
    validated = file_ops.validate_path(str(test_file))
    # resolve() resolves symlinks, so paths should be equivalent
    assert validated.resolve() == test_file.resolve()


def test_validate_path_traversal_blocked(file_ops, temp_dir):
    """Test path traversal is blocked."""
    with pytest.raises(SecurityError, match="Path traversal detected"):
        file_ops.validate_path(f"{temp_dir}/../etc/passwd")


def test_validate_path_outside_allowed_dirs(file_ops):
    """Test path outside allowed directories is blocked."""
    with pytest.raises(SecurityError, match="Path outside allowed directories"):
        file_ops.validate_path("/etc/passwd")


@pytest.mark.asyncio
async def test_read_file(file_ops, temp_dir):
    """Test reading file."""
    test_file = Path(temp_dir) / "test.txt"
    test_content = b"Hello, World!"
    test_file.write_bytes(test_content)

    content = await file_ops.read_file(str(test_file))
    assert content == test_content


@pytest.mark.asyncio
async def test_read_file_not_found(file_ops, temp_dir):
    """Test reading non-existent file."""
    with pytest.raises(FileNotFoundError):
        await file_ops.read_file(str(Path(temp_dir) / "nonexistent.txt"))


@pytest.mark.asyncio
async def test_write_file(file_ops, temp_dir):
    """Test writing file with safe permissions."""
    test_file = Path(temp_dir) / "output.txt"
    test_content = b"Test content"

    await file_ops.write_file(str(test_file), test_content)

    assert test_file.exists()
    assert test_file.read_bytes() == test_content

    # Check permissions (0600 = owner read/write only)
    stat_info = test_file.stat()
    permissions = stat_info.st_mode & 0o777
    assert permissions == 0o600


@pytest.mark.asyncio
async def test_write_file_custom_permissions(file_ops, temp_dir):
    """Test writing file with custom permissions."""
    test_file = Path(temp_dir) / "custom.txt"
    test_content = b"Custom content"

    await file_ops.write_file(str(test_file), test_content, permissions=0o644)

    stat_info = test_file.stat()
    permissions = stat_info.st_mode & 0o777
    assert permissions == 0o644


@pytest.mark.asyncio
async def test_list_directory(file_ops, temp_dir):
    """Test listing directory contents."""
    # Create test files
    (Path(temp_dir) / "file1.txt").write_text("test1")
    (Path(temp_dir) / "file2.txt").write_text("test2")
    (Path(temp_dir) / "subdir").mkdir()

    files = await file_ops.list_directory(temp_dir)

    assert len(files) == 3
    assert "file1.txt" in files
    assert "file2.txt" in files
    assert "subdir" in files


@pytest.mark.asyncio
async def test_list_directory_not_found(file_ops, temp_dir):
    """Test listing non-existent directory."""
    with pytest.raises(FileNotFoundError):
        await file_ops.list_directory(str(Path(temp_dir) / "nonexistent"))


@pytest.mark.asyncio
async def test_file_size_limit(temp_dir):
    """Test file size limit enforcement."""
    config = ServerConfig(
        server_name="test-server",
        environment="dev",
        allowed_file_directories=[temp_dir],
        max_file_size_mb=1,  # 1MB limit
    )
    file_ops = FileOperations(config)

    # Create a file larger than limit (2MB)
    large_file = Path(temp_dir) / "large.txt"
    large_file.write_bytes(b"x" * (2 * 1024 * 1024))

    with pytest.raises(SecurityError, match="File too large"):
        await file_ops.read_file(str(large_file))


@pytest.mark.asyncio
async def test_write_to_disallowed_directory():
    """Test writing to disallowed directory is blocked."""
    config = ServerConfig(server_name="test-server", environment="dev", allowed_file_directories=["/tmp"])
    file_ops = FileOperations(config)

    with pytest.raises(SecurityError, match="Path outside allowed directories"):
        await file_ops.write_file("/etc/test.txt", b"content")


def test_default_permissions(file_ops):
    """Test default permissions are set correctly."""
    assert file_ops.default_permissions == 0o600


def test_max_file_size(file_ops):
    """Test max file size is set from config."""
    assert file_ops.max_size_bytes == 100 * 1024 * 1024  # 100MB in bytes


# ============================================================================
# Additional Security Tests (From CODE_REVIEW.md)
# ============================================================================


@pytest.mark.asyncio
async def test_file_ops_toctou_protection(temp_dir):
    """Test time-of-check-time-of-use protection."""
    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Create legitimate file
    test_path = Path(temp_dir) / "test_toctou.txt"
    test_path.write_text("legitimate")

    # First read should succeed
    content = await file_ops.read_file(str(test_path))
    assert content == b"legitimate"

    # Simulate symlink replacement attack
    restricted_file = Path("/etc") / "passwd"

    # Replace with symlink to restricted file
    test_path.unlink()
    test_path.symlink_to(restricted_file)

    # Second read should detect symlink escape
    with pytest.raises(SecurityError, match="outside allowed"):
        await file_ops.read_file(str(test_path))

    # Cleanup
    if test_path.exists():
        test_path.unlink()


@pytest.mark.asyncio
async def test_file_ops_symlink_escape(temp_dir):
    """Test symlink cannot escape allowed directories."""
    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Create symlink pointing outside allowed directory
    test_symlink = Path(temp_dir) / "escape_link"
    test_symlink.symlink_to("/etc/passwd")

    try:
        with pytest.raises(SecurityError, match="outside allowed"):
            await file_ops.read_file(str(test_symlink))
    finally:
        if test_symlink.exists():
            test_symlink.unlink()


@pytest.mark.asyncio
async def test_file_ops_large_file_handling(temp_dir):
    """Test large file handling."""
    config = ServerConfig(
        server_name="test",
        allowed_file_directories=[temp_dir],
        environment="dev",
        max_file_size_mb=50,  # 50MB limit
    )
    file_ops = FileOperations(config)

    # Create a 60MB file (exceeds limit)
    large_file = Path(temp_dir) / "large.bin"
    large_content = b"x" * (60 * 1024 * 1024)

    # Writing large content should fail
    with pytest.raises(SecurityError, match="too large"):
        await file_ops.write_file(str(large_file), large_content)

    # Create a 30MB file (within limit)
    medium_file = Path(temp_dir) / "medium.bin"
    medium_content = b"x" * (30 * 1024 * 1024)

    # Writing medium content should succeed
    await file_ops.write_file(str(medium_file), medium_content)
    assert medium_file.exists()
    assert medium_file.stat().st_size == 30 * 1024 * 1024


@pytest.mark.asyncio
async def test_file_ops_concurrent_operations(temp_dir):
    """Test concurrent file operations."""
    import asyncio

    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Create multiple files concurrently
    async def write_file(index: int):
        file_path = Path(temp_dir) / f"concurrent_{index}.txt"
        await file_ops.write_file(str(file_path), f"content_{index}".encode())
        return index

    # Write 10 files concurrently
    tasks = [write_file(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10

    # Verify all files were created
    for i in range(10):
        file_path = Path(temp_dir) / f"concurrent_{i}.txt"
        assert file_path.exists()
        content = await file_ops.read_file(str(file_path))
        assert content == f"content_{i}".encode()


@pytest.mark.asyncio
async def test_file_ops_permission_validation_on_write(temp_dir):
    """Test permission validation on write."""
    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Write file with default permissions (0600)
    default_file = Path(temp_dir) / "default_perms.txt"
    await file_ops.write_file(str(default_file), b"default")

    # Check permissions
    stat_info = default_file.stat()
    permissions = stat_info.st_mode & 0o777
    assert permissions == 0o600

    # Write file with custom permissions (0644)
    custom_file = Path(temp_dir) / "custom_perms.txt"
    await file_ops.write_file(str(custom_file), b"custom", permissions=0o644)

    # Check permissions
    stat_info = custom_file.stat()
    permissions = stat_info.st_mode & 0o777
    assert permissions == 0o644

    # Write file with restrictive permissions (0400 - read-only)
    readonly_file = Path(temp_dir) / "readonly.txt"
    await file_ops.write_file(str(readonly_file), b"readonly", permissions=0o400)

    # Check permissions
    stat_info = readonly_file.stat()
    permissions = stat_info.st_mode & 0o777
    assert permissions == 0o400


@pytest.mark.asyncio
async def test_file_ops_symlink_in_path(temp_dir):
    """Test handling of symlinks in path components."""
    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Create a subdirectory and a file in it
    subdir = Path(temp_dir) / "subdir"
    subdir.mkdir()
    target_file = subdir / "target.txt"
    target_file.write_text("target content")

    # Create a symlink to the subdirectory
    symlink_dir = Path(temp_dir) / "link_to_subdir"
    symlink_dir.symlink_to(subdir)

    # Access file through symlink should work (within allowed directory)
    symlink_file = symlink_dir / "target.txt"
    content = await file_ops.read_file(str(symlink_file))
    assert content == b"target content"

    # Cleanup
    symlink_dir.unlink()


@pytest.mark.asyncio
async def test_file_ops_write_toctou_protection(temp_dir):
    """Test TOCTOU protection on write operations."""
    config = ServerConfig(server_name="test", allowed_file_directories=[temp_dir], environment="dev")
    file_ops = FileOperations(config)

    # Create a legitimate file path
    test_path = Path(temp_dir) / "test_write_toctou.txt"

    # Write should succeed
    await file_ops.write_file(str(test_path), b"initial content")
    assert test_path.exists()

    # Replace with symlink pointing outside allowed directory
    test_path.unlink()
    test_path.symlink_to("/etc/passwd")

    # Write should fail due to TOCTOU check after write
    with pytest.raises(SecurityError, match="outside allowed"):
        await file_ops.write_file(str(test_path), b"malicious content")

    # Cleanup
    if test_path.exists():
        test_path.unlink()
