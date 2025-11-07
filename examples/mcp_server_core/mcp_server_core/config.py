"""Configuration management for MCP servers.

Loads configuration from environment variables with type safety via Pydantic.
All settings use the MCP_ prefix (e.g., MCP_SERVER_NAME).
"""

from typing import Literal, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Base configuration for MCP servers.

    All values loaded from environment variables with MCP_ prefix.
    Create .env file or set environment variables.

    Example .env:
        MCP_SERVER_NAME=my-server
        MCP_TRANSPORT=stdio
        MCP_LOG_LEVEL=INFO
        MCP_ENVIRONMENT=production
    """

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars
    )

    # Server identity
    server_name: str = Field(description="MCP server name (displayed to clients)")
    environment: Literal["dev", "staging", "production"] = Field(default="production", description="Deployment environment")

    # Transport and Logging
    transport: Literal["stdio", "http"] = Field(
        default="stdio", description="MCP transport protocol (stdio for local, http with streaming for cloud)"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path (for STDIO mode, defaults to /tmp/mcp-{server_name}.log)")
    log_include_payloads: bool = Field(default=False, description="Include request/response payloads in logs (dev only)")

    # HTTP transport settings (only used if transport=http)
    http_host: str = Field(default="0.0.0.0", description="HTTP server bind address")
    http_port: int = Field(default=8000, description="HTTP server port")

    # Error handling
    mask_error_details: bool = Field(default=True, description="Mask internal error details in production")
    include_traceback: bool = Field(default=False, description="Include stack traces in errors (dev only)")

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting middleware")
    rate_limit_requests_per_second: float = Field(default=10.0, description="Maximum requests per second")
    rate_limit_burst_capacity: int = Field(default=20, description="Burst capacity for rate limiting")

    # Retry configuration
    retry_enabled: bool = Field(default=True, description="Enable automatic retry middleware")
    retry_max_attempts: int = Field(default=3, description="Maximum retry attempts")

    # Observability (optional)
    enable_tracing: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    enable_metrics: bool = Field(default=False, description="Enable Prometheus metrics")
    otlp_endpoint: Optional[str] = Field(default=None, description="OpenTelemetry collector endpoint (e.g., http://localhost:4317)")
    prometheus_port: Optional[int] = Field(default=None, description="Prometheus metrics endpoint port (e.g., 9090)")

    # Security - File operations
    allowed_file_directories: list[str] = Field(default_factory=lambda: ["/tmp", "./data"], description="Allowed directories for file operations")
    max_file_size_mb: int = Field(default=100, description="Maximum file size in megabytes")
    file_default_permissions: Union[int, str] = Field(default=0o600, description="Default file permissions (octal, e.g., 0600 or 0o600)")

    # Security - URL fetching
    url_allow_private_ips: bool = Field(default=False, description="Allow fetching from private IP ranges (SSRF protection)")
    url_require_https: bool = Field(default=True, description="Require HTTPS for URL fetching (production)")
    url_max_size_mb: int = Field(default=10, description="Maximum response size for URL fetching in megabytes")
    url_timeout_seconds: int = Field(default=30, description="Timeout for URL fetching in seconds")

    @field_validator("file_default_permissions", mode="before")
    @classmethod
    def parse_octal_permissions(cls, v: Union[int, str]) -> int:
        """Parse file permissions from octal string or int.

        Accepts:
        - Octal strings: "0600", "0644", "0755"
        - Python octal literals: 0o600 (when set in code)
        - Decimal integers: 384 (equivalent to 0o600)
        """
        if isinstance(v, str):
            # Parse as octal if it looks like octal notation
            if v.startswith("0") and len(v) > 1 and v[1:].isdigit():
                return int(v, 8)  # Parse as octal
            return int(v)  # Parse as decimal
        return v

    @field_validator("log_file", mode="after")
    @classmethod
    def set_default_log_file(cls, v: Optional[str], info) -> str:
        """Set default log file path if not provided."""
        transport = info.data.get("transport", "stdio")  # Provide default
        if v is None and transport == "stdio":
            server_name = info.data.get("server_name", "mcp-server")
            return f"/tmp/mcp-{server_name}.log"
        return v or ""

    @field_validator("include_traceback", mode="after")
    @classmethod
    def validate_traceback_setting(cls, v: bool, info) -> bool:
        """Warn if traceback enabled in production."""
        if v and info.data.get("environment") == "production":
            import warnings

            warnings.warn("include_traceback=True in production environment. This may expose sensitive internal details.")
        return v

    @field_validator("url_require_https", mode="after")
    @classmethod
    def validate_https_setting(cls, v: bool, info) -> bool:
        """Require HTTPS in production."""
        if not v and info.data.get("environment") == "production":
            raise ValueError("url_require_https must be True in production environment")
        return v

    def get_log_file_path(self) -> Optional[str]:
        """Get the log file path if STDIO transport is used."""
        if self.transport == "stdio":
            return self.log_file
        return None
