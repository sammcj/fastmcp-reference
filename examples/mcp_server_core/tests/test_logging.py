"""Tests for logging configuration."""

import logging
import tempfile
from pathlib import Path

from mcp_server_core.config import ServerConfig
from mcp_server_core.logging import configure_logging, get_logger


def test_configure_logging_stdio_mode():
    """Test logging configuration for STDIO mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = str(Path(tmpdir) / "test.log")
        config = ServerConfig(server_name="test-server", transport="stdio", log_file=log_file, log_level="DEBUG")

        middleware = configure_logging(config)

        assert middleware is not None
        assert Path(log_file).exists()

        # Check logging level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG


def test_configure_logging_http_mode():
    """Test logging configuration for HTTP mode."""
    config = ServerConfig(server_name="test-server", transport="http", log_level="INFO")

    middleware = configure_logging(config)

    assert middleware is not None

    # Check logging level
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_get_logger():
    """Test get_logger function."""
    logger = get_logger("test_module")

    assert logger is not None
    assert logger.name == "test_module"
    assert isinstance(logger, logging.Logger)


def test_logging_middleware_configuration():
    """Test StructuredLoggingMiddleware configuration."""
    config = ServerConfig(server_name="test-server", transport="stdio", log_include_payloads=True)

    middleware = configure_logging(config)

    # StructuredLoggingMiddleware should be configured with include_payloads
    assert hasattr(middleware, "include_payloads")


def test_logging_file_created_in_parent_dir():
    """Test that log file is created in parent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = str(Path(tmpdir) / "subdir" / "test.log")
        config = ServerConfig(server_name="test-server", transport="stdio", log_file=log_file)

        configure_logging(config)

        # Parent directory should be created
        assert Path(log_file).parent.exists()
        assert Path(log_file).exists()
