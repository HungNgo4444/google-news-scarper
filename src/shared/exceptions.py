"""Enhanced custom exceptions with error classification for the Google News Scraper application."""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    """Error codes for classification and handling."""
    # Business logic errors
    CATEGORY_NOT_FOUND = "CATEGORY_NOT_FOUND"
    CATEGORY_VALIDATION_FAILED = "CATEGORY_VALIDATION_FAILED"
    INVALID_KEYWORDS = "INVALID_KEYWORDS"
    
    # External service errors
    GOOGLE_NEWS_UNAVAILABLE = "GOOGLE_NEWS_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    EXTRACTION_TIMEOUT = "EXTRACTION_TIMEOUT"
    EXTRACTION_NETWORK_ERROR = "EXTRACTION_NETWORK_ERROR"
    
    # Infrastructure errors
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    REDIS_CONNECTION_ERROR = "REDIS_CONNECTION_ERROR"
    CELERY_TASK_FAILED = "CELERY_TASK_FAILED"
    
    # Generic errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class BaseAppException(Exception):
    """Enhanced base exception with error classification and retry information."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
        retry_after: Optional[int] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and serialization."""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
            "retry_after": self.retry_after,
            "type": self.__class__.__name__
        }


# Business Logic Errors
class BusinessLogicError(BaseAppException):
    """Base class for business logic errors."""
    pass


class CategoryValidationError(BusinessLogicError):
    """Raised when category validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.CATEGORY_VALIDATION_FAILED,
            message=message,
            details=details,
            retryable=False
        )


class CategoryNotFoundError(BusinessLogicError):
    """Raised when a category is not found."""
    
    def __init__(self, category_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"Category not found: {category_id}"
        super().__init__(
            code=ErrorCode.CATEGORY_NOT_FOUND,
            message=message,
            details=details or {"category_id": category_id},
            retryable=False
        )


class DuplicateCategoryNameError(CategoryValidationError):
    """Raised when attempting to create a category with duplicate name."""
    
    def __init__(self, category_name: str, details: Optional[Dict[str, Any]] = None):
        message = f"Category name already exists: {category_name}"
        super().__init__(
            message=message,
            details=details or {"category_name": category_name}
        )


class InvalidKeywordsError(BusinessLogicError):
    """Raised when keywords are invalid."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.INVALID_KEYWORDS,
            message=message,
            details=details,
            retryable=False
        )


# External Service Errors
class ExternalServiceError(BaseAppException):
    """Base class for external service errors."""
    pass


class GoogleNewsUnavailableError(ExternalServiceError):
    """Raised when Google News service is unavailable."""
    
    def __init__(self, message: str = "Google News service unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.GOOGLE_NEWS_UNAVAILABLE,
            message=message,
            details=details,
            retryable=True,
            retry_after=300  # 5 minutes default
        )


class RateLimitExceededError(ExternalServiceError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            details=details,
            retryable=True,
            retry_after=retry_after or 60
        )


class ExtractionError(ExternalServiceError):
    """Base exception for article extraction failures."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = True):
        super().__init__(
            code=ErrorCode.EXTRACTION_FAILED,
            message=message,
            details=details,
            retryable=retryable,
            retry_after=60
        )


class ExtractionTimeoutError(ExtractionError):
    """Raised when article extraction times out."""
    
    def __init__(self, url: str, timeout: int, details: Optional[Dict[str, Any]] = None):
        message = f"Extraction timeout for {url} after {timeout}s"
        super().__init__(
            message=message,
            details=details or {"url": url, "timeout": timeout},
            retryable=True
        )
        self.code = ErrorCode.EXTRACTION_TIMEOUT


class ExtractionParsingError(ExtractionError):
    """Raised when article content cannot be parsed."""
    
    def __init__(self, url: str, details: Optional[Dict[str, Any]] = None):
        message = f"Failed to parse article content from {url}"
        super().__init__(
            message=message,
            details=details or {"url": url},
            retryable=False
        )


class ExtractionNetworkError(ExtractionError):
    """Raised when network-related extraction errors occur."""
    
    def __init__(self, url: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Network error extracting from {url}"
        if status_code:
            message += f" (status: {status_code})"
        
        super().__init__(
            message=message,
            details=details or {"url": url, "status_code": status_code},
            retryable=True
        )
        self.code = ErrorCode.EXTRACTION_NETWORK_ERROR


# Infrastructure Errors
class InfrastructureError(BaseAppException):
    """Base class for infrastructure errors."""
    pass


class DatabaseConnectionError(InfrastructureError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str = "Database connection failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.DATABASE_CONNECTION_ERROR,
            message=message,
            details=details,
            retryable=True,
            retry_after=30
        )


class RedisConnectionError(InfrastructureError):
    """Raised when Redis connection fails."""
    
    def __init__(self, message: str = "Redis connection failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.REDIS_CONNECTION_ERROR,
            message=message,
            details=details,
            retryable=True,
            retry_after=30
        )


class CeleryTaskFailedError(InfrastructureError):
    """Raised when Celery task fails unexpectedly."""
    
    def __init__(self, task_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.CELERY_TASK_FAILED,
            message=f"Task {task_name} failed: {message}",
            details=details or {"task_name": task_name},
            retryable=True,
            retry_after=60
        )


# Generic Errors
class InternalServerError(BaseAppException):
    """Raised for unexpected internal server errors."""
    
    def __init__(self, message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            details=details,
            retryable=False
        )


class ValidationError(BaseAppException):
    """Raised for validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details=details,
            retryable=False
        )


# Circuit Breaker and Reliability Errors
class CircuitBreakerOpenError(InfrastructureError):
    """Raised when circuit breaker is open."""

    def __init__(self, service_name: str, details: Optional[Dict[str, Any]] = None):
        message = f"Circuit breaker is open for service: {service_name}"
        super().__init__(
            code=ErrorCode.INTERNAL_SERVER_ERROR,  # Using existing error code
            message=message,
            details=details or {"service_name": service_name},
            retryable=True,
            retry_after=30
        )


class CrawlerError(ExternalServiceError):
    """General crawler error for backward compatibility."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = True):
        super().__init__(
            code=ErrorCode.EXTRACTION_FAILED,
            message=message,
            details=details,
            retryable=retryable,
            retry_after=60
        )


# Legacy exceptions for backward compatibility
BaseScraperError = BaseAppException  # Alias for backward compatibility
ConfigurationError = ValidationError  # Map to ValidationError