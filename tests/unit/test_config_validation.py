"""Unit tests for configuration validation and environment variable handling.

This test suite validates that the Pydantic Settings configuration can handle
all 80+ environment variables without validation errors, supporting both
development and production environments.
"""

import os
import pytest
from unittest.mock import patch
from src.shared.config import Settings, get_settings


class TestConfigurationValidation:
    """Test suite for configuration validation and environment handling."""

    def test_settings_loads_without_validation_errors(self):
        """Test that Settings class loads all environment variables without validation errors."""
        # This test verifies the fix for the original 80 validation errors
        settings = Settings()
        assert settings is not None
        assert isinstance(settings.DATABASE_URL, str)

    def test_all_env_variables_accessible(self):
        """Test that all 80+ environment variables are accessible as Settings fields."""
        settings = get_settings()

        # Test critical environment variables that were causing validation errors
        critical_vars = [
            # PostgreSQL Configuration
            "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
            "POSTGRES_MAX_CONNECTIONS", "POSTGRES_SHARED_BUFFERS",

            # Docker Resource Limits
            "WEB_CPU_LIMIT", "WEB_MEMORY_LIMIT", "WORKER_CPU_LIMIT",
            "POSTGRES_CPU_LIMIT", "REDIS_CPU_LIMIT",

            # SSL/Security
            "SSL_CERT_PATH", "SSL_KEY_PATH",

            # Monitoring
            "FLOWER_USERNAME", "FLOWER_PASSWORD",

            # Development/Production Settings
            "DEV_RELOAD", "DEV_DEBUG", "DEV_CORS_ORIGINS",
            "PROD_ALLOWED_HOSTS", "PROD_CORS_ORIGINS",

            # Feature Flags
            "ENABLE_API_DOCS", "ENABLE_FLOWER_MONITORING"
        ]

        for var_name in critical_vars:
            # Each variable should be accessible without AttributeError
            value = getattr(settings, var_name, None)
            assert value is not None, f"Environment variable {var_name} not accessible"

    def test_development_environment_configuration(self):
        """Test configuration loading in development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            get_settings.cache_clear()  # Clear cache to reload settings
            settings = get_settings()

            assert settings.ENVIRONMENT == "development"
            assert settings.DEV_RELOAD is True
            assert settings.DEV_DEBUG is True
            # CORS origins should be parsed as JSON string
            assert "localhost:3000" in settings.DEV_CORS_ORIGINS

    def test_production_environment_configuration(self):
        """Test configuration loading in production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            get_settings.cache_clear()  # Clear cache to reload settings
            settings = get_settings()

            assert settings.ENVIRONMENT == "production"
            assert settings.PROD_SECURE_SSL_REDIRECT is True
            assert settings.PROD_SESSION_COOKIE_SECURE is True
            assert "https://" in settings.PROD_CORS_ORIGINS

    def test_database_url_validation(self):
        """Test DATABASE_URL field validation."""
        settings = get_settings()

        # Should start with postgresql:// or postgresql+asyncpg://
        assert (settings.DATABASE_URL.startswith("postgresql://") or
                settings.DATABASE_URL.startswith("postgresql+asyncpg://"))

    def test_cors_configuration_for_frontend(self):
        """Test CORS configuration for frontend integration."""
        settings = get_settings()

        # Development CORS should include frontend ports
        dev_cors = settings.DEV_CORS_ORIGINS
        assert "3000" in dev_cors or "3001" in dev_cors, "CORS not configured for frontend ports"

    def test_feature_flags_configuration(self):
        """Test that feature flags are properly configured."""
        settings = get_settings()

        # API docs should be enabled by default
        assert settings.ENABLE_API_DOCS is True

        # Flower monitoring should be enabled by default
        assert settings.ENABLE_FLOWER_MONITORING is True

    def test_docker_resource_limits_configuration(self):
        """Test Docker resource limits are properly configured."""
        settings = get_settings()

        # Web container limits
        assert settings.WEB_CPU_LIMIT == "1.0"
        assert settings.WEB_MEMORY_LIMIT == "512M"

        # PostgreSQL container limits
        assert settings.POSTGRES_CPU_LIMIT == "2.0"
        assert settings.POSTGRES_MEMORY_LIMIT == "2G"

    def test_logging_configuration(self):
        """Test logging configuration fields."""
        settings = get_settings()

        assert settings.LOG_FORMAT in ["json", "text"]
        assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert settings.DATABASE_LOG_LEVEL == "WARNING"
        assert settings.API_LOG_LEVEL == "INFO"

    def test_backup_configuration(self):
        """Test backup configuration fields."""
        settings = get_settings()

        assert settings.BACKUP_ENABLED is True
        assert settings.BACKUP_SCHEDULE == "0 2 * * *"
        assert settings.BACKUP_RETENTION_DAYS == 30

    @pytest.mark.parametrize("env_name,expected_type", [
        ("API_PORT", int),
        ("DATABASE_POOL_SIZE", int),
        ("EXTRACTION_TIMEOUT", int),
        ("POSTGRES_DB", str),
        ("REDIS_MAX_MEMORY", str),
        ("DEV_RELOAD", bool),
        ("BACKUP_ENABLED", bool),
        # Story 2.5 - URL Processing Limits
        ("MAX_URLS_TO_PROCESS", int),
        ("MAX_RESULTS_PER_SEARCH", int),
        ("MAX_TABS_PER_BROWSER", int),
    ])
    def test_field_types(self, env_name, expected_type):
        """Test that environment variable fields have correct types."""
        settings = get_settings()
        value = getattr(settings, env_name)
        assert isinstance(value, expected_type), f"{env_name} should be {expected_type}, got {type(value)}"

    def test_url_processing_limits_configuration(self):
        """Test URL processing limits configuration (Story 2.5)."""
        settings = get_settings()

        # Test default values
        assert settings.MAX_URLS_TO_PROCESS == 100, "MAX_URLS_TO_PROCESS should default to 100"
        assert settings.MAX_RESULTS_PER_SEARCH == 200, "MAX_RESULTS_PER_SEARCH should default to 200"
        assert settings.MAX_TABS_PER_BROWSER == 20, "MAX_TABS_PER_BROWSER should default to 20"

    def test_url_processing_limits_validation(self):
        """Test validation of URL processing limits (Story 2.5)."""
        # Test MAX_URLS_TO_PROCESS validation
        with pytest.raises(ValueError, match="MAX_URLS_TO_PROCESS must be positive"):
            Settings(MAX_URLS_TO_PROCESS=0)

        with pytest.raises(ValueError, match="MAX_URLS_TO_PROCESS must not exceed 500"):
            Settings(MAX_URLS_TO_PROCESS=600)

        # Test MAX_RESULTS_PER_SEARCH validation
        with pytest.raises(ValueError, match="MAX_RESULTS_PER_SEARCH must be positive"):
            Settings(MAX_RESULTS_PER_SEARCH=-1)

        with pytest.raises(ValueError, match="MAX_RESULTS_PER_SEARCH must not exceed 1000"):
            Settings(MAX_RESULTS_PER_SEARCH=1500)

        # Test MAX_TABS_PER_BROWSER validation
        with pytest.raises(ValueError, match="MAX_TABS_PER_BROWSER must be positive"):
            Settings(MAX_TABS_PER_BROWSER=0)

        with pytest.raises(ValueError, match="MAX_TABS_PER_BROWSER must not exceed 50"):
            Settings(MAX_TABS_PER_BROWSER=100)

    def test_url_processing_limits_within_valid_range(self):
        """Test that URL processing limits accept valid values (Story 2.5)."""
        # Test valid values - should not raise exceptions
        settings = Settings(
            MAX_URLS_TO_PROCESS=150,
            MAX_RESULTS_PER_SEARCH=300,
            MAX_TABS_PER_BROWSER=25
        )

        assert settings.MAX_URLS_TO_PROCESS == 150
        assert settings.MAX_RESULTS_PER_SEARCH == 300
        assert settings.MAX_TABS_PER_BROWSER == 25