"""Tests for retry handler with exponential backoff."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Any

from src.core.error_handling.retry_handler import (
    RetryConfig,
    RetryHandler,
    retry_with_backoff,
    EXTERNAL_SERVICE_RETRY,
    DATABASE_RETRY,
    RATE_LIMIT_RETRY
)
from src.shared.exceptions import (
    BaseAppException,
    ExternalServiceError,
    RateLimitExceededError,
    DatabaseConnectionError,
    ValidationError,
    ErrorCode
)


class TestRetryConfig:
    """Tests for RetryConfig class."""
    
    def test_default_retry_config(self):
        """Test default retry configuration values."""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter_range == 0.5
        assert config.retryable_exceptions == (BaseAppException,)
        assert config.non_retryable_exceptions == ()
    
    def test_custom_retry_config(self):
        """Test custom retry configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=1.5,
            jitter_range=0.3,
            retryable_exceptions=(ExternalServiceError,),
            non_retryable_exceptions=(ValidationError,)
        )
        
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 1.5
        assert config.jitter_range == 0.3
        assert config.retryable_exceptions == (ExternalServiceError,)
        assert config.non_retryable_exceptions == (ValidationError,)
    
    def test_predefined_configs(self):
        """Test predefined retry configurations."""
        # External service retry config
        assert EXTERNAL_SERVICE_RETRY.max_retries == 3
        assert EXTERNAL_SERVICE_RETRY.base_delay == 1.0
        assert EXTERNAL_SERVICE_RETRY.max_delay == 300.0
        
        # Database retry config
        assert DATABASE_RETRY.max_retries == 2
        assert DATABASE_RETRY.base_delay == 0.5
        assert DATABASE_RETRY.max_delay == 30.0
        
        # Rate limit retry config
        assert RATE_LIMIT_RETRY.max_retries == 5
        assert RATE_LIMIT_RETRY.base_delay == 60.0
        assert RATE_LIMIT_RETRY.max_delay == 3600.0


class TestRetryHandler:
    """Tests for RetryHandler class."""
    
    @pytest.fixture
    def retry_handler(self):
        """Create retry handler for testing."""
        config = RetryConfig(
            max_retries=3,
            base_delay=0.1,  # Small delay for tests
            max_delay=1.0,
            exponential_base=2.0,
            jitter_range=0.1  # Small jitter for predictability
        )
        return RetryHandler(config)
    
    def test_retry_handler_initialization(self):
        """Test retry handler initialization."""
        config = RetryConfig(max_retries=5)
        handler = RetryHandler(config)
        
        assert handler.config is config
        assert handler.config.max_retries == 5
    
    def test_retry_handler_default_config(self):
        """Test retry handler with default config."""
        handler = RetryHandler()
        
        assert handler.config.max_retries == 3
        assert handler.config.base_delay == 1.0
    
    def test_calculate_delay_no_attempt(self, retry_handler):
        """Test delay calculation for first attempt (attempt 0)."""
        delay = retry_handler.calculate_delay(0)
        
        # Should be close to base_delay (0.1) with small jitter
        assert 0.05 <= delay <= 0.15
    
    def test_calculate_delay_exponential_backoff(self, retry_handler):
        """Test exponential backoff delay calculation."""
        delay1 = retry_handler.calculate_delay(1, base_delay=1.0)
        delay2 = retry_handler.calculate_delay(2, base_delay=1.0)
        delay3 = retry_handler.calculate_delay(3, base_delay=1.0)
        
        # Should show exponential growth (with jitter)
        # Attempt 1: ~2s, Attempt 2: ~4s, Attempt 3: ~8s
        assert 1.5 <= delay1 <= 2.5
        assert 3.0 <= delay2 <= 5.0
        # But capped at max_delay (1.0 for test)
        assert delay3 <= 1.1  # Small tolerance for jitter
    
    def test_calculate_delay_max_cap(self, retry_handler):
        """Test that delay is capped at max_delay."""
        delay = retry_handler.calculate_delay(10)  # Very high attempt
        
        # Should be capped at max_delay (1.0) plus jitter tolerance
        assert delay <= 1.1
    
    def test_calculate_delay_minimum(self, retry_handler):
        """Test that delay has a minimum value."""
        # Use negative jitter to test minimum
        with patch('random.uniform', return_value=-1.0):  # Maximum negative jitter
            delay = retry_handler.calculate_delay(0)
            assert delay >= 0.1  # Should be at least 0.1s
    
    def test_should_retry_max_attempts_exceeded(self, retry_handler):
        """Test should_retry returns False when max attempts exceeded."""
        exception = ExternalServiceError(code="TEST", message="Test error")
        
        # Should retry for attempts 0, 1, 2
        assert retry_handler.should_retry(exception, 0) is True
        assert retry_handler.should_retry(exception, 1) is True
        assert retry_handler.should_retry(exception, 2) is True
        
        # Should not retry for attempt 3 (exceeds max_retries=3)
        assert retry_handler.should_retry(exception, 3) is False
    
    def test_should_retry_non_retryable_exception(self):
        """Test should_retry with non-retryable exception."""
        config = RetryConfig(non_retryable_exceptions=(ValidationError,))
        handler = RetryHandler(config)
        
        non_retryable = ValidationError("Invalid input")
        retryable = ExternalServiceError(code="TEST", message="Service error")
        
        assert handler.should_retry(non_retryable, 0) is False
        assert handler.should_retry(retryable, 0) is True
    
    def test_should_retry_base_app_exception_retryable_flag(self, retry_handler):
        """Test should_retry respects BaseAppException retryable flag."""
        retryable_exception = ExternalServiceError(
            code="TEST",
            message="Retryable error",
            retryable=True
        )
        
        non_retryable_exception = ValidationError(
            "Non-retryable error",
            details={"field": "test"}
        )  # ValidationError has retryable=False by default
        
        assert retry_handler.should_retry(retryable_exception, 0) is True
        assert retry_handler.should_retry(non_retryable_exception, 0) is False
    
    def test_should_retry_retryable_exceptions_check(self):
        """Test should_retry with retryable_exceptions configuration."""
        config = RetryConfig(retryable_exceptions=(ExternalServiceError,))
        handler = RetryHandler(config)
        
        external_error = ExternalServiceError(code="TEST", message="External error")
        other_error = ValueError("Standard Python error")
        
        assert handler.should_retry(external_error, 0) is True
        assert handler.should_retry(other_error, 0) is False
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self, retry_handler):
        """Test successful execution on first attempt."""
        mock_func = AsyncMock(return_value="success")
        
        result = await retry_handler.execute_with_retry(
            mock_func,
            "arg1",
            kwarg1="value1",
            correlation_id="test-123"
        )
        
        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with("arg1", kwarg1="value1")
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_failures(self, retry_handler):
        """Test successful execution after some failures."""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceError(code="TEMP_ERROR", message="Temporary error")
            return "finally_success"
        
        result = await retry_handler.execute_with_retry(flaky_func)
        
        assert result == "finally_success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self, retry_handler):
        """Test when all retry attempts fail."""
        mock_func = AsyncMock(side_effect=ExternalServiceError(
            code="PERSISTENT_ERROR",
            message="Persistent error"
        ))
        
        with pytest.raises(ExternalServiceError) as exc_info:
            await retry_handler.execute_with_retry(mock_func)
        
        assert exc_info.value.message == "Persistent error"
        assert mock_func.call_count == 4  # Initial + 3 retries
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_error(self, retry_handler):
        """Test that non-retryable errors are not retried."""
        mock_func = AsyncMock(side_effect=ValidationError("Invalid input"))
        
        with pytest.raises(ValidationError):
            await retry_handler.execute_with_retry(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_sync_function(self, retry_handler):
        """Test retry handler with synchronous function."""
        call_count = 0
        
        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError(code="TEMP", message="Temporary")
            return "sync_success"
        
        result = await retry_handler.execute_with_retry(sync_func)
        
        assert result == "sync_success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_respects_retry_after(self, retry_handler):
        """Test that retry_after from exception is respected."""
        exception_with_retry_after = RateLimitExceededError(
            "Rate limited",
            retry_after=0.2  # 200ms
        )
        
        call_count = 0
        start_time = time.time()
        
        async def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise exception_with_retry_after
            return "success_after_wait"
        
        result = await retry_handler.execute_with_retry(rate_limited_func)
        elapsed = time.time() - start_time
        
        assert result == "success_after_wait"
        assert elapsed >= 0.18  # Should have waited at least close to retry_after
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_correlation_id_logging(self, retry_handler, caplog):
        """Test that correlation ID is included in log messages."""
        mock_func = AsyncMock(return_value="success")
        correlation_id = "test-correlation-456"
        
        await retry_handler.execute_with_retry(mock_func, correlation_id=correlation_id)
        
        # Check that correlation ID appears in logs
        log_messages = [record.message for record in caplog.records]
        assert any(correlation_id in msg for msg in log_messages)


class TestRetryDecorator:
    """Tests for retry_with_backoff decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_async_function(self):
        """Test retry decorator with async function."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def decorated_async_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError(code="TEMP", message="Temporary error")
            return "decorated_success"
        
        result = await decorated_async_func()
        
        assert result == "decorated_success"
        assert call_count == 2
    
    def test_retry_decorator_sync_function(self):
        """Test retry decorator with sync function."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def decorated_sync_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError(code="TEMP", message="Temporary error")
            return "decorated_sync_success"
        
        result = decorated_sync_func()
        
        assert result == "decorated_sync_success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_decorator_custom_exceptions(self):
        """Test retry decorator with custom retryable exceptions."""
        @retry_with_backoff(
            max_retries=1,
            retryable_exceptions=(RateLimitExceededError,)
        )
        async def rate_limited_func():
            raise ValidationError("This should not be retried")
        
        with pytest.raises(ValidationError):
            await rate_limited_func()
    
    @pytest.mark.asyncio
    async def test_retry_decorator_with_parameters(self):
        """Test retry decorator preserves function parameters."""
        call_count = 0
        
        @retry_with_backoff(max_retries=1, base_delay=0.01)
        async def parameterized_func(x, y, z=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError(code="TEMP", message="Temporary")
            return f"x={x}, y={y}, z={z}"
        
        result = await parameterized_func("a", "b", z="c")
        
        assert result == "x=a, y=b, z=c"
        assert call_count == 2


class TestRetryIntegration:
    """Integration tests for retry functionality."""
    
    @pytest.mark.asyncio
    async def test_retry_with_different_error_types(self):
        """Test retry behavior with different error types."""
        config = RetryConfig(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError, DatabaseConnectionError)
        )
        handler = RetryHandler(config)
        
        # Test retryable errors
        retryable_errors = [
            ExternalServiceError(code="TEMP", message="External error"),
            DatabaseConnectionError("DB connection failed"),
            RateLimitExceededError("Rate limited")  # Inherits from ExternalServiceError
        ]
        
        for error in retryable_errors:
            call_count = 0
            
            async def error_func():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise error
                return "recovered"
            
            result = await handler.execute_with_retry(error_func)
            assert result == "recovered"
            assert call_count == 2
        
        # Test non-retryable error
        async def non_retryable_func():
            raise ValidationError("Non-retryable")
        
        with pytest.raises(ValidationError):
            await handler.execute_with_retry(non_retryable_func)
    
    @pytest.mark.asyncio
    async def test_retry_delay_progression(self):
        """Test that retry delays follow exponential backoff."""
        config = RetryConfig(
            max_retries=3,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            jitter_range=0.0  # No jitter for predictable testing
        )
        handler = RetryHandler(config)
        
        delays = []
        call_times = []
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_times.append(time.time())
            call_count += 1
            raise ExternalServiceError(code="PERSISTENT", message="Always fails")
        
        start_time = time.time()
        
        with pytest.raises(ExternalServiceError):
            await handler.execute_with_retry(failing_func)
        
        # Calculate actual delays between calls
        for i in range(1, len(call_times)):
            delay = call_times[i] - call_times[i-1]
            delays.append(delay)
        
        # Verify exponential backoff pattern (with some tolerance)
        assert len(delays) == 3  # Should have 3 retry delays
        assert delays[0] >= 0.08  # ~0.1s (base_delay * 2^0)
        assert delays[1] >= 0.18  # ~0.2s (base_delay * 2^1)
        assert delays[2] >= 0.38  # ~0.4s (base_delay * 2^2)
    
    @pytest.mark.asyncio
    async def test_retry_with_mixed_success_failure(self):
        """Test retry behavior with mixed success/failure patterns."""
        handler = RetryHandler(RetryConfig(max_retries=5, base_delay=0.01))
        
        # Pattern: fail, fail, succeed, fail, succeed
        call_count = 0
        success_pattern = [False, False, True, False, True]
        
        async def mixed_pattern_func():
            nonlocal call_count
            result = success_pattern[call_count] if call_count < len(success_pattern) else False
            call_count += 1
            
            if not result:
                raise ExternalServiceError(code="INTERMITTENT", message="Intermittent failure")
            return f"success_on_attempt_{call_count}"
        
        result = await handler.execute_with_retry(mixed_pattern_func)
        
        assert result == "success_on_attempt_3"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_retry_operations(self):
        """Test multiple concurrent retry operations."""
        handler = RetryHandler(RetryConfig(max_retries=2, base_delay=0.01))
        
        async def flaky_service(service_id: str):
            # Each service fails once then succeeds
            if not hasattr(flaky_service, 'failures'):
                flaky_service.failures = set()
            
            if service_id not in flaky_service.failures:
                flaky_service.failures.add(service_id)
                raise ExternalServiceError(code="TEMP", message=f"Service {service_id} failing")
            
            return f"Service {service_id} OK"
        
        # Run multiple services concurrently
        tasks = [
            handler.execute_with_retry(flaky_service, f"service_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        expected_results = [f"Service service_{i} OK" for i in range(5)]
        assert results == expected_results
    
    def test_predefined_retry_configs_usage(self):
        """Test using predefined retry configurations."""
        # Test external service config
        external_handler = RetryHandler(EXTERNAL_SERVICE_RETRY)
        assert external_handler.config.max_retries == 3
        assert external_handler.config.max_delay == 300.0
        
        # Test database config
        db_handler = RetryHandler(DATABASE_RETRY)
        assert db_handler.config.max_retries == 2
        assert db_handler.config.base_delay == 0.5
        
        # Test rate limit config
        rate_limit_handler = RetryHandler(RATE_LIMIT_RETRY)
        assert rate_limit_handler.config.max_retries == 5
        assert rate_limit_handler.config.base_delay == 60.0


class TestRetryErrorScenarios:
    """Tests for various error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_retry_with_exception_chaining(self, retry_handler):
        """Test that exception chaining is preserved through retries."""
        async def func_with_chained_exception():
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise ExternalServiceError(
                    code="CHAINED",
                    message="Chained error"
                ) from e
        
        with pytest.raises(ExternalServiceError) as exc_info:
            await retry_handler.execute_with_retry(func_with_chained_exception)
        
        assert exc_info.value.message == "Chained error"
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)
    
    @pytest.mark.asyncio
    async def test_retry_with_function_raising_different_exceptions(self, retry_handler):
        """Test retry behavior when function raises different exception types."""
        call_count = 0
        
        async def changing_exception_func():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise ExternalServiceError(code="TEMP1", message="First error")
            elif call_count == 2:
                raise DatabaseConnectionError("Second error")
            else:
                raise ValidationError("Non-retryable error")
        
        with pytest.raises(ValidationError):
            await retry_handler.execute_with_retry(changing_exception_func)
        
        assert call_count == 3  # Two retryable attempts + one non-retryable
    
    @pytest.mark.asyncio
    async def test_retry_handler_with_zero_max_retries(self):
        """Test retry handler with zero max retries."""
        config = RetryConfig(max_retries=0)
        handler = RetryHandler(config)
        
        mock_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Error"))
        
        with pytest.raises(ExternalServiceError):
            await handler.execute_with_retry(mock_func)
        
        assert mock_func.call_count == 1  # Only initial call, no retries
    
    @pytest.mark.asyncio
    async def test_retry_with_keyboard_interrupt(self, retry_handler):
        """Test that KeyboardInterrupt is not retried."""
        mock_func = AsyncMock(side_effect=KeyboardInterrupt())
        
        with pytest.raises(KeyboardInterrupt):
            await retry_handler.execute_with_retry(mock_func)
        
        assert mock_func.call_count == 1  # Should not retry system interrupts