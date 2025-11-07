"""Tests for custom exceptions."""

from fastmcp.exceptions import ToolError

from mcp_server_core.exceptions import SecurityError


def test_security_error():
    """Test SecurityError exception."""
    error = SecurityError("SSRF attempt detected")
    assert str(error) == "SSRF attempt detected"
    assert isinstance(error, Exception)
    assert isinstance(error, ToolError)


def test_security_error_inheritance():
    """Test SecurityError inherits from ToolError."""
    error = SecurityError("Test error")
    assert isinstance(error, ToolError)
    assert isinstance(error, Exception)


def test_security_error_can_be_raised_and_caught():
    """Test that SecurityError can be raised and caught."""
    try:
        raise SecurityError("Test security error")
    except SecurityError as e:
        assert "Test security error" in str(e)

    # Can also be caught as ToolError
    try:
        raise SecurityError("Another test")
    except ToolError as e:
        assert "Another test" in str(e)
