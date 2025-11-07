"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from mcp_server_core.config import ServerConfig


def test_config_defaults():
    """Test default configuration values."""
    config = ServerConfig(server_name="test-server")

    assert config.server_name == "test-server"
    assert config.environment == "production"
    assert config.transport == "stdio"
    assert config.log_level == "INFO"
    assert config.rate_limit_enabled is True
    assert config.retry_enabled is True
    assert config.url_require_https is True
    assert config.mask_error_details is True


def test_config_custom_values():
    """Test custom configuration values."""
    config = ServerConfig(
        server_name="custom-server",
        environment="dev",
        transport="http",
        log_level="DEBUG",
        http_host="0.0.0.0",
        http_port=9000,
        rate_limit_requests_per_second=20.0,
    )

    assert config.server_name == "custom-server"
    assert config.environment == "dev"
    assert config.transport == "http"
    assert config.log_level == "DEBUG"
    assert config.http_host == "0.0.0.0"
    assert config.http_port == 9000
    assert config.rate_limit_requests_per_second == 20.0


def test_config_log_file_default():
    """Test default log file path for STDIO mode."""
    config = ServerConfig(server_name="test-server", transport="stdio")
    assert config.log_file == "/tmp/mcp-test-server.log"


def test_config_log_file_custom():
    """Test custom log file path."""
    config = ServerConfig(server_name="test-server", transport="stdio", log_file="/custom/path/server.log")
    assert config.log_file == "/custom/path/server.log"


def test_config_https_required_in_production():
    """Test that HTTPS is required in production."""
    with pytest.raises(ValidationError, match="url_require_https must be True"):
        ServerConfig(server_name="test-server", environment="production", url_require_https=False)


def test_config_https_not_required_in_dev():
    """Test that HTTPS is not required in dev."""
    config = ServerConfig(server_name="test-server", environment="dev", url_require_https=False)
    assert config.url_require_https is False


def test_config_traceback_warning_in_production():
    """Test warning when traceback enabled in production."""
    with pytest.warns(UserWarning, match="include_traceback=True in production"):
        ServerConfig(server_name="test-server", environment="production", include_traceback=True)


def test_config_get_log_file_path_stdio():
    """Test get_log_file_path for STDIO mode."""
    config = ServerConfig(server_name="test-server", transport="stdio")
    assert config.get_log_file_path() == "/tmp/mcp-test-server.log"


def test_config_get_log_file_path_http():
    """Test get_log_file_path for HTTP mode."""
    config = ServerConfig(server_name="test-server", transport="http")
    assert config.get_log_file_path() is None


def test_config_allowed_file_directories():
    """Test allowed file directories configuration."""
    config = ServerConfig(server_name="test-server", allowed_file_directories=["/custom/path", "/another/path"])
    assert config.allowed_file_directories == ["/custom/path", "/another/path"]


def test_config_security_defaults():
    """Test security-related defaults."""
    config = ServerConfig(server_name="test-server")

    # File operations
    assert config.allowed_file_directories == ["/tmp", "./data"]
    assert config.max_file_size_mb == 100
    assert config.file_default_permissions == 0o600

    # URL fetching
    assert config.url_allow_private_ips is False
    assert config.url_require_https is True
    assert config.url_max_size_mb == 10
    assert config.url_timeout_seconds == 30


def test_config_octal_permissions_parsing():
    """Test parsing of octal permission strings."""
    # Octal string (standard chmod notation)
    config1 = ServerConfig(server_name="test-server", file_default_permissions="0600")
    assert config1.file_default_permissions == 0o600  # 384 decimal

    # Another octal string
    config2 = ServerConfig(server_name="test-server", file_default_permissions="0644")
    assert config2.file_default_permissions == 0o644  # 420 decimal

    # Decimal integer
    config3 = ServerConfig(server_name="test-server", file_default_permissions=384)
    assert config3.file_default_permissions == 384

    # Python octal literal (in code, not env var)
    config4 = ServerConfig(server_name="test-server", file_default_permissions=0o755)
    assert config4.file_default_permissions == 0o755  # 493 decimal
