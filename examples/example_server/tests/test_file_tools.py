"""Tests for file tools."""

import pytest
from pathlib import Path
import tempfile

from tools.file_tools import FileTools
from mcp_server_core.exceptions import SecurityError


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def file_tools(temp_dir, test_config):
    """Create FileTools instance with temp directory allowed."""
    test_config.allowed_file_directories = [temp_dir, "/tmp"]
    from mcp_server_core.abstractions import FileOperations

    file_ops = FileOperations(test_config)
    return FileTools(file_ops)


@pytest.mark.asyncio
async def test_read_file(file_tools, temp_dir, mock_context):
    """Test reading file."""
    test_file = Path(temp_dir) / "test.txt"
    test_content = "Hello, World!"
    test_file.write_text(test_content)

    result = await file_tools.read_file(str(test_file), mock_context)

    assert result["path"] == str(test_file)
    assert result["content"] == test_content
    assert result["size"] == len(test_content.encode())

    # Verify logging
    mock_context.info.assert_called()


@pytest.mark.asyncio
async def test_read_file_not_found(file_tools, temp_dir, mock_context):
    """Test reading non-existent file."""
    with pytest.raises(FileNotFoundError):
        await file_tools.read_file(str(Path(temp_dir) / "nonexistent.txt"), mock_context)


@pytest.mark.asyncio
async def test_read_file_outside_allowed_dirs(file_tools, mock_context):
    """Test reading file outside allowed directories."""
    with pytest.raises(SecurityError, match="Path outside allowed directories"):
        await file_tools.read_file("/etc/passwd", mock_context)


@pytest.mark.asyncio
async def test_write_file(file_tools, temp_dir, mock_context):
    """Test writing file."""
    test_file = Path(temp_dir) / "output.txt"
    test_content = "Test content"

    result = await file_tools.write_file(str(test_file), test_content, mock_context)

    assert result["path"] == str(test_file)
    assert result["bytes_written"] == len(test_content.encode())
    assert result["permissions"] == "0600 (owner read/write only)"

    # Verify file was written
    assert test_file.exists()
    assert test_file.read_text() == test_content

    # Verify logging
    mock_context.info.assert_called()


@pytest.mark.asyncio
async def test_write_file_creates_parent_dirs(file_tools, temp_dir, mock_context):
    """Test writing file creates parent directories."""
    test_file = Path(temp_dir) / "subdir" / "output.txt"
    test_content = "Test content"

    result = await file_tools.write_file(str(test_file), test_content, mock_context)

    assert result["path"] == str(test_file)
    assert test_file.exists()
    assert test_file.parent.exists()


@pytest.mark.asyncio
async def test_write_file_outside_allowed_dirs(file_tools, mock_context):
    """Test writing file outside allowed directories."""
    with pytest.raises(SecurityError, match="Path outside allowed directories"):
        await file_tools.write_file("/etc/test.txt", "content", mock_context)


@pytest.mark.asyncio
async def test_list_directory(file_tools, temp_dir, mock_context):
    """Test listing directory."""
    # Create test files
    (Path(temp_dir) / "file1.txt").write_text("test1")
    (Path(temp_dir) / "file2.txt").write_text("test2")
    (Path(temp_dir) / "subdir").mkdir()

    result = await file_tools.list_directory(temp_dir, mock_context)

    assert result["path"] == temp_dir
    assert result["count"] == 3
    assert "file1.txt" in result["files"]
    assert "file2.txt" in result["files"]
    assert "subdir" in result["files"]

    # Verify logging
    mock_context.info.assert_called()


@pytest.mark.asyncio
async def test_list_directory_not_found(file_tools, temp_dir, mock_context):
    """Test listing non-existent directory."""
    with pytest.raises(FileNotFoundError):
        await file_tools.list_directory(str(Path(temp_dir) / "nonexistent"), mock_context)


@pytest.mark.asyncio
async def test_list_directory_outside_allowed_dirs(file_tools, mock_context):
    """Test listing directory outside allowed directories."""
    with pytest.raises(SecurityError, match="Path outside allowed directories"):
        await file_tools.list_directory("/etc", mock_context)
