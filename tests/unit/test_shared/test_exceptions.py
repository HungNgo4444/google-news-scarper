"""Tests for enhanced exception handling system."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any

from src.shared.exceptions import (
    ErrorCode,
    BaseAppException,
    BusinessLogicError,
    CategoryValidationError,
    CategoryNotFoundError,
    InvalidKeywordsError,
    ExternalServiceError,
    GoogleNewsUnavailableError,
    RateLimitExceededError,
    ExtractionError,
    ExtractionTimeoutError,
    ExtractionParsingError,
    ExtractionNetworkError,
    InfrastructureError,
    DatabaseConnectionError,
    RedisConnectionError,
    CeleryTaskFailedError,
    InternalServerError,
    ValidationError
)


class TestErrorCode:
    """Tests for ErrorCode enum."""
    
    def test_error_code_values(self):
        """Test that error codes have correct string values."""
        assert ErrorCode.CATEGORY_NOT_FOUND.value == "CATEGORY_NOT_FOUND"
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == "RATE_LIMIT_EXCEEDED"
        assert ErrorCode.GOOGLE_NEWS_UNAVAILABLE.value == "GOOGLE_NEWS_UNAVAILABLE"
        assert ErrorCode.DATABASE_CONNECTION_ERROR.value == "DATABASE_CONNECTION_ERROR"
        assert ErrorCode.INTERNAL_SERVER_ERROR.value == "INTERNAL_SERVER_ERROR"
    
    def test_error_code_enum_membership(self):
        """Test error code enum membership."""
        # Business logic errors
        assert ErrorCode.CATEGORY_NOT_FOUND in ErrorCode
        assert ErrorCode.INVALID_KEYWORDS in ErrorCode
        
        # External service errors
        assert ErrorCode.EXTRACTION_FAILED in ErrorCode
        assert ErrorCode.EXTRACTION_TIMEOUT in ErrorCode
        
        # Infrastructure errors
        assert ErrorCode.CELERY_TASK_FAILED in ErrorCode
        assert ErrorCode.REDIS_CONNECTION_ERROR in ErrorCode


class TestBaseAppException:
    """Tests for BaseAppException class."""
    
    def test_basic_exception_creation(self):
        """Test basic exception creation with required parameters."""
        exc = BaseAppException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="Test error message"
        )
        
        assert exc.code == ErrorCode.INTERNAL_SERVER_ERROR
        assert exc.message == "Test error message"
        assert exc.details == {}
        assert exc.retryable is False
        assert exc.retry_after is None
        assert str(exc) == "Test error message"
    
    def test_exception_with_full_parameters(self):
        """Test exception creation with all parameters."""
        details = {"key": "value", "count": 42}
        
        exc = BaseAppException(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded",
            details=details,
            retryable=True,
            retry_after=300
        )
        
        assert exc.code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.message == "Rate limit exceeded"
        assert exc.details == details
        assert exc.retryable is True
        assert exc.retry_after == 300
    
    def test_to_dict_method(self):
        """Test exception serialization to dictionary."""
        details = {"url": "https://example.com", "status": 500}
        
        exc = BaseAppException(
            code=ErrorCode.EXTRACTION_FAILED,
            message="Extraction failed",
            details=details,
            retryable=True,
            retry_after=60
        )
        
        result = exc.to_dict()
        
        expected = {
            "code": "EXTRACTION_FAILED",
            "message": "Extraction failed",
            "details": details,
            "retryable": True,
            "retry_after": 60,
            "type": "BaseAppException"
        }
        
        assert result == expected
    
    def test_exception_inheritance(self):
        """Test that BaseAppException inherits from Exception properly."""
        exc = BaseAppException(
            code=ErrorCode.VALIDATION_ERROR,
            message="Validation failed"
        )
        
        assert isinstance(exc, Exception)
        assert isinstance(exc, BaseAppException)


class TestBusinessLogicErrors:
    """Tests for business logic error classes."""
    
    def test_category_validation_error(self):
        """Test CategoryValidationError creation and properties."""
        details = {"field": "name", "reason": "too_short"}
        
        exc = CategoryValidationError("Category name too short", details)
        
        assert exc.code == ErrorCode.CATEGORY_VALIDATION_FAILED
        assert exc.message == "Category name too short"
        assert exc.details == details
        assert exc.retryable is False
        assert isinstance(exc, BusinessLogicError)
        assert isinstance(exc, BaseAppException)
    
    def test_category_not_found_error(self):
        """Test CategoryNotFoundError creation and properties."""
        category_id = "123e4567-e89b-12d3-a456-426614174000"
        
        exc = CategoryNotFoundError(category_id)
        
        assert exc.code == ErrorCode.CATEGORY_NOT_FOUND
        assert exc.message == f"Category not found: {category_id}"
        assert exc.details == {"category_id": category_id}
        assert exc.retryable is False
    
    def test_category_not_found_error_with_details(self):
        """Test CategoryNotFoundError with additional details."""
        category_id = "test-id"
        additional_details = {"attempted_at": "2024-01-01T00:00:00Z"}
        
        exc = CategoryNotFoundError(category_id, additional_details)
        
        assert exc.details == additional_details
    
    def test_invalid_keywords_error(self):
        """Test InvalidKeywordsError creation."""
        details = {"invalid_keywords": ["", "toolong" * 50]}
        
        exc = InvalidKeywordsError("Keywords validation failed", details)
        
        assert exc.code == ErrorCode.INVALID_KEYWORDS
        assert exc.message == "Keywords validation failed"
        assert exc.details == details
        assert exc.retryable is False


class TestExternalServiceErrors:
    """Tests for external service error classes."""
    
    def test_google_news_unavailable_error_default(self):
        """Test GoogleNewsUnavailableError with default parameters."""
        exc = GoogleNewsUnavailableError()
        
        assert exc.code == ErrorCode.GOOGLE_NEWS_UNAVAILABLE
        assert exc.message == "Google News service unavailable"
        assert exc.retryable is True
        assert exc.retry_after == 300
        assert isinstance(exc, ExternalServiceError)
    
    def test_google_news_unavailable_error_custom(self):
        """Test GoogleNewsUnavailableError with custom parameters."""
        details = {"status_code": 503, "response": "Service temporarily unavailable"}
        
        exc = GoogleNewsUnavailableError("Custom message", details)
        
        assert exc.message == "Custom message"
        assert exc.details == details
    
    def test_rate_limit_exceeded_error(self):
        """Test RateLimitExceededError creation."""
        exc = RateLimitExceededError("Too many requests", retry_after=1800)
        
        assert exc.code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.message == "Too many requests"
        assert exc.retryable is True
        assert exc.retry_after == 1800
    
    def test_rate_limit_exceeded_error_default_retry(self):
        """Test RateLimitExceededError with default retry_after."""
        exc = RateLimitExceededError("Rate limit hit")
        
        assert exc.retry_after == 60  # Default value
    
    def test_extraction_error(self):
        """Test base ExtractionError class."""
        details = {"url": "https://example.com", "attempt": 1}
        
        exc = ExtractionError("Failed to extract content", details, retryable=False)
        
        assert exc.code == ErrorCode.EXTRACTION_FAILED
        assert exc.message == "Failed to extract content"
        assert exc.details == details
        assert exc.retryable is False
        assert exc.retry_after == 60
    
    def test_extraction_timeout_error(self):
        """Test ExtractionTimeoutError creation."""
        url = "https://slow-site.com"
        timeout = 30
        
        exc = ExtractionTimeoutError(url, timeout)
        
        assert exc.code == ErrorCode.EXTRACTION_TIMEOUT
        assert exc.message == f"Extraction timeout for {url} after {timeout}s"
        assert exc.details == {"url": url, "timeout": timeout}
        assert exc.retryable is True
    
    def test_extraction_parsing_error(self):
        """Test ExtractionParsingError creation."""
        url = "https://malformed.com"
        
        exc = ExtractionParsingError(url)
        
        assert exc.message == f"Failed to parse article content from {url}"
        assert exc.details == {"url": url}
        assert exc.retryable is False
    
    def test_extraction_network_error(self):
        """Test ExtractionNetworkError creation."""
        url = "https://unreachable.com"
        status_code = 404
        
        exc = ExtractionNetworkError(url, status_code)
        
        assert exc.code == ErrorCode.EXTRACTION_NETWORK_ERROR
        assert exc.message == f"Network error extracting from {url} (status: {status_code})"
        assert exc.details == {"url": url, "status_code": status_code}
        assert exc.retryable is True
    
    def test_extraction_network_error_no_status(self):
        """Test ExtractionNetworkError without status code."""
        url = "https://timeout.com"
        
        exc = ExtractionNetworkError(url)
        
        assert exc.message == f"Network error extracting from {url}"
        assert exc.details == {"url": url, "status_code": None}


class TestInfrastructureErrors:
    """Tests for infrastructure error classes."""
    
    def test_database_connection_error_default(self):
        """Test DatabaseConnectionError with default parameters."""
        exc = DatabaseConnectionError()
        
        assert exc.code == ErrorCode.DATABASE_CONNECTION_ERROR
        assert exc.message == "Database connection failed"
        assert exc.retryable is True
        assert exc.retry_after == 30
        assert isinstance(exc, InfrastructureError)
    
    def test_database_connection_error_custom(self):
        """Test DatabaseConnectionError with custom parameters."""
        details = {"host": "db.example.com", "port": 5432}
        
        exc = DatabaseConnectionError("Connection timeout", details)
        
        assert exc.message == "Connection timeout"
        assert exc.details == details
    
    def test_redis_connection_error(self):
        """Test RedisConnectionError creation."""
        exc = RedisConnectionError("Redis server not responding")
        
        assert exc.code == ErrorCode.REDIS_CONNECTION_ERROR
        assert exc.message == "Redis server not responding"
        assert exc.retryable is True
        assert exc.retry_after == 30
    
    def test_celery_task_failed_error(self):
        """Test CeleryTaskFailedError creation."""
        task_name = "crawl_category_task"
        message = "Task crashed unexpectedly"
        details = {"worker": "worker-1", "queue": "default"}
        
        exc = CeleryTaskFailedError(task_name, message, details)
        
        assert exc.code == ErrorCode.CELERY_TASK_FAILED
        assert exc.message == f"Task {task_name} failed: {message}"
        assert exc.details == {"task_name": task_name, **details}
        assert exc.retryable is True
        assert exc.retry_after == 60


class TestGenericErrors:
    """Tests for generic error classes."""
    
    def test_internal_server_error_default(self):
        """Test InternalServerError with default parameters."""
        exc = InternalServerError()
        
        assert exc.code == ErrorCode.INTERNAL_SERVER_ERROR
        assert exc.message == "Internal server error"
        assert exc.retryable is False
    
    def test_internal_server_error_custom(self):
        """Test InternalServerError with custom parameters."""
        details = {"component": "scheduler", "operation": "job_creation"}
        
        exc = InternalServerError("Scheduler component failed", details)
        
        assert exc.message == "Scheduler component failed"
        assert exc.details == details
    
    def test_validation_error(self):
        """Test ValidationError creation."""
        details = {"field": "keywords", "value": []}
        
        exc = ValidationError("Keywords cannot be empty", details)
        
        assert exc.code == ErrorCode.VALIDATION_ERROR
        assert exc.message == "Keywords cannot be empty"
        assert exc.details == details
        assert exc.retryable is False


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""
    
    def test_exception_hierarchy_business_logic(self):
        """Test business logic exception hierarchy."""
        exc = CategoryValidationError("Test")
        
        assert isinstance(exc, CategoryValidationError)
        assert isinstance(exc, BusinessLogicError)
        assert isinstance(exc, BaseAppException)
        assert isinstance(exc, Exception)
    
    def test_exception_hierarchy_external_service(self):
        """Test external service exception hierarchy."""
        exc = GoogleNewsUnavailableError("Test")
        
        assert isinstance(exc, GoogleNewsUnavailableError)
        assert isinstance(exc, ExternalServiceError)
        assert isinstance(exc, BaseAppException)
        assert isinstance(exc, Exception)
    
    def test_exception_hierarchy_extraction(self):
        """Test extraction exception hierarchy."""
        exc = ExtractionTimeoutError("http://test.com", 30)
        
        assert isinstance(exc, ExtractionTimeoutError)
        assert isinstance(exc, ExtractionError)
        assert isinstance(exc, ExternalServiceError)
        assert isinstance(exc, BaseAppException)
        assert isinstance(exc, Exception)
    
    def test_exception_hierarchy_infrastructure(self):
        """Test infrastructure exception hierarchy."""
        exc = DatabaseConnectionError("Test")
        
        assert isinstance(exc, DatabaseConnectionError)
        assert isinstance(exc, InfrastructureError)
        assert isinstance(exc, BaseAppException)
        assert isinstance(exc, Exception)


class TestExceptionSerialization:
    """Tests for exception serialization and logging compatibility."""
    
    def test_exception_dict_contains_all_fields(self):
        """Test that to_dict includes all necessary fields."""
        exc = RateLimitExceededError(
            "Rate limit hit",
            retry_after=1800,
            details={"limit": 1000, "window": 3600}
        )
        
        result = exc.to_dict()
        
        required_fields = ["code", "message", "details", "retryable", "retry_after", "type"]
        
        for field in required_fields:
            assert field in result
    
    def test_exception_dict_json_serializable(self):
        """Test that exception dict can be JSON serialized."""
        import json
        
        exc = ExtractionNetworkError(
            "https://test.com",
            status_code=500,
            details={"timestamp": datetime.now().isoformat()}
        )
        
        result = exc.to_dict()
        
        # Should not raise an exception
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["code"] == "EXTRACTION_NETWORK_ERROR"
    
    def test_exception_str_representation(self):
        """Test string representation of exceptions."""
        exc = CategoryNotFoundError("cat-123")
        
        assert str(exc) == "Category not found: cat-123"
        assert repr(exc).startswith("CategoryNotFoundError")


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy exceptions."""
    
    def test_base_scraper_error_alias(self):
        """Test BaseScraperError alias for backward compatibility."""
        from src.shared.exceptions import BaseScraperError
        
        assert BaseScraperError is BaseAppException
        
        # Should work as before
        exc = BaseScraperError(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="Legacy error"
        )
        
        assert isinstance(exc, BaseAppException)
    
    def test_configuration_error_mapping(self):
        """Test ConfigurationError mapping to ValidationError."""
        from src.shared.exceptions import ConfigurationError
        
        assert ConfigurationError is ValidationError
        
        # Should work as a ValidationError
        exc = ConfigurationError("Config invalid")
        
        assert isinstance(exc, ValidationError)
        assert exc.code == ErrorCode.VALIDATION_ERROR


# Integration tests for error handling patterns

class TestErrorHandlingPatterns:
    """Tests for common error handling patterns."""
    
    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing error logging."""
        return Mock()
    
    def test_exception_context_preservation(self):
        """Test that exception context is preserved through chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise ExtractionError(
                    "Extraction failed due to parsing error",
                    details={"original_error": str(e)},
                    retryable=False
                ) from e
        except ExtractionError as exc:
            assert exc.message == "Extraction failed due to parsing error"
            assert exc.details["original_error"] == "Original error"
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)
    
    def test_retry_decision_based_on_exception_properties(self):
        """Test retry decision logic based on exception properties."""
        retryable_errors = [
            GoogleNewsUnavailableError(),
            RateLimitExceededError("Rate limit"),
            ExtractionNetworkError("http://test.com", 500),
            DatabaseConnectionError()
        ]
        
        non_retryable_errors = [
            CategoryNotFoundError("cat-123"),
            ExtractionParsingError("http://test.com"),
            ValidationError("Invalid input")
        ]
        
        for exc in retryable_errors:
            assert exc.retryable is True, f"{type(exc).__name__} should be retryable"
        
        for exc in non_retryable_errors:
            assert exc.retryable is False, f"{type(exc).__name__} should not be retryable"
    
    def test_error_categorization_for_monitoring(self):
        """Test that exceptions can be categorized for monitoring."""
        business_errors = [CategoryNotFoundError("test"), InvalidKeywordsError("test")]
        external_errors = [GoogleNewsUnavailableError(), RateLimitExceededError("test")]
        infrastructure_errors = [DatabaseConnectionError(), RedisConnectionError()]
        
        for exc in business_errors:
            assert isinstance(exc, BusinessLogicError)
        
        for exc in external_errors:
            assert isinstance(exc, ExternalServiceError)
        
        for exc in infrastructure_errors:
            assert isinstance(exc, InfrastructureError)
    
    def test_exception_details_for_debugging(self):
        """Test that exceptions contain sufficient details for debugging."""
        exc = ExtractionTimeoutError(
            url="https://slow-site.com/article/123",
            timeout=30,
            details={
                "user_agent": "GoogleBot",
                "attempt": 3,
                "total_attempts": 5
            }
        )
        
        details = exc.to_dict()
        
        # Should contain all debugging information
        assert "url" in details["details"]
        assert "timeout" in details["details"]
        assert "user_agent" in details["details"]
        assert "attempt" in details["details"]
        assert details["retryable"] is True
        assert details["type"] == "ExtractionTimeoutError"