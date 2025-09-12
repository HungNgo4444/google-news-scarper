"""Retry handler with exponential backoff and jitter for failed operations."""

import asyncio
import random
import time
from typing import Any, Callable, Dict, Optional, Type, Union, Tuple
import logging
from functools import wraps

from src.shared.exceptions import BaseAppException, ErrorCode

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter_range: float = 0.5,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        non_retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter_range = jitter_range  # ±50% jitter by default
        self.retryable_exceptions = retryable_exceptions or (BaseAppException,)
        self.non_retryable_exceptions = non_retryable_exceptions or ()


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def calculate_delay(self, attempt: int, base_delay: Optional[float] = None) -> float:
        """Calculate delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (0-based)
            base_delay: Override base delay for this calculation
            
        Returns:
            Delay in seconds with jitter applied
        """
        if base_delay is None:
            base_delay = self.config.base_delay
        
        # Calculate exponential backoff
        delay = base_delay * (self.config.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.config.max_delay)
        
        # Apply jitter (±jitter_range percentage)
        jitter = random.uniform(-self.config.jitter_range, self.config.jitter_range)
        delay = delay * (1 + jitter)
        
        # Ensure positive delay
        return max(0.1, delay)
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-based)
            
        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exceeded max retries
        if attempt >= self.config.max_retries:
            return False
        
        # Check for non-retryable exceptions first
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # For BaseAppException, check retryable flag
        if isinstance(exception, BaseAppException):
            return exception.retryable
        
        # Check for retryable exceptions
        return isinstance(exception, self.config.retryable_exceptions)
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute a function with retry logic.
        
        Args:
            func: Function to execute (sync or async)
            *args: Arguments for the function
            correlation_id: Correlation ID for logging
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
            
        Raises:
            Last exception if all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.info(
                    f"Executing {func.__name__}, attempt {attempt + 1}/{self.config.max_retries + 1}",
                    extra={
                        "correlation_id": correlation_id,
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_attempts": self.config.max_retries + 1
                    }
                )
                
                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - log and return
                if attempt > 0:
                    logger.info(
                        f"Function {func.__name__} succeeded on attempt {attempt + 1}",
                        extra={
                            "correlation_id": correlation_id,
                            "function": func.__name__,
                            "successful_attempt": attempt + 1
                        }
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Log the exception
                logger.warning(
                    f"Function {func.__name__} failed on attempt {attempt + 1}: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                
                # Check if we should retry
                if not self.should_retry(e, attempt):
                    logger.error(
                        f"Not retrying {func.__name__} due to non-retryable error or max attempts reached",
                        extra={
                            "correlation_id": correlation_id,
                            "function": func.__name__,
                            "final_error": str(e),
                            "total_attempts": attempt + 1
                        }
                    )
                    raise e
                
                # Calculate delay for next attempt
                if attempt < self.config.max_retries:
                    # Check if exception specifies retry_after
                    if isinstance(e, BaseAppException) and e.retry_after:
                        delay = e.retry_after
                        logger.info(f"Using exception-specified retry delay: {delay}s")
                    else:
                        delay = self.calculate_delay(attempt)
                    
                    logger.info(
                        f"Retrying {func.__name__} in {delay:.2f} seconds",
                        extra={
                            "correlation_id": correlation_id,
                            "function": func.__name__,
                            "delay": delay,
                            "next_attempt": attempt + 2
                        }
                    )
                    
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(
            f"All retries exhausted for {func.__name__}",
            extra={
                "correlation_id": correlation_id,
                "function": func.__name__,
                "total_attempts": self.config.max_retries + 1,
                "final_error": str(last_exception)
            }
        )
        raise last_exception


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter_range: float = 0.5,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """Decorator for automatic retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        jitter_range: Jitter range as percentage (0.5 = ±50%)
        retryable_exceptions: Tuple of retryable exception types
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter_range=jitter_range,
                retryable_exceptions=retryable_exceptions
            )
            handler = RetryHandler(config)
            return await handler.execute_with_retry(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter_range=jitter_range,
                retryable_exceptions=retryable_exceptions
            )
            handler = RetryHandler(config)
            return asyncio.run(handler.execute_with_retry(func, *args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Predefined retry configurations for common scenarios
EXTERNAL_SERVICE_RETRY = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=300.0,  # 5 minutes
    exponential_base=2.0,
    jitter_range=0.5
)

DATABASE_RETRY = RetryConfig(
    max_retries=2,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter_range=0.3
)

RATE_LIMIT_RETRY = RetryConfig(
    max_retries=5,
    base_delay=60.0,  # Start with 1 minute
    max_delay=3600.0,  # Max 1 hour
    exponential_base=1.5,  # Slower growth
    jitter_range=0.2
)