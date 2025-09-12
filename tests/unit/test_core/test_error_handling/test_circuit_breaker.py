"""Tests for circuit breaker pattern implementation."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import replace

from src.core.error_handling.circuit_breaker import (
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    get_circuit_breaker_manager,
    circuit_breaker
)
from src.shared.exceptions import ExternalServiceError, GoogleNewsUnavailableError


class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration."""
    
    def test_default_config_values(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 300
        assert config.success_threshold == 3
        assert config.timeout_duration is None
        assert config.monitored_exceptions == (ExternalServiceError,)
    
    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=600,
            success_threshold=5,
            timeout_duration=30,
            monitored_exceptions=(GoogleNewsUnavailableError,)
        )
        
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 600
        assert config.success_threshold == 5
        assert config.timeout_duration == 30
        assert config.monitored_exceptions == (GoogleNewsUnavailableError,)


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics."""
    
    def test_default_metrics(self):
        """Test default metrics initialization."""
        metrics = CircuitBreakerMetrics()
        
        assert metrics.failure_count == 0
        assert metrics.success_count == 0
        assert metrics.last_failure_time is None
        assert metrics.last_success_time is None
        assert metrics.total_calls == 0
        assert metrics.total_failures == 0
        assert metrics.total_successes == 0
        assert isinstance(metrics.state_change_time, float)
    
    def test_metrics_update(self):
        """Test metrics can be updated."""
        metrics = CircuitBreakerMetrics()
        
        # Update metrics
        metrics.failure_count = 3
        metrics.success_count = 2
        metrics.total_calls = 10
        
        assert metrics.failure_count == 3
        assert metrics.success_count == 2
        assert metrics.total_calls == 10


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""
    
    def test_circuit_breaker_open_error_creation(self):
        """Test CircuitBreakerOpenError creation."""
        service_name = "test_service"
        next_retry_time = time.time() + 300
        
        error = CircuitBreakerOpenError(service_name, next_retry_time)
        
        assert "Circuit breaker open for test_service" in error.message
        assert error.details["service_name"] == service_name
        assert error.details["next_retry_time"] == next_retry_time
        assert error.details["circuit_breaker_state"] == "open"
        assert error.retryable is True
        assert error.retry_after > 0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            success_threshold=2
        )
        return CircuitBreaker("test_service", config)
    
    def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test circuit breaker starts in closed state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert not circuit_breaker.is_half_open
        assert circuit_breaker.metrics.failure_count == 0
        assert circuit_breaker.metrics.success_count == 0
    
    def test_circuit_breaker_properties(self, circuit_breaker):
        """Test circuit breaker state properties."""
        # Closed state
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert not circuit_breaker.is_half_open
        
        # Open state
        circuit_breaker.state = CircuitBreakerState.OPEN
        assert not circuit_breaker.is_closed
        assert circuit_breaker.is_open
        assert not circuit_breaker.is_half_open
        
        # Half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        assert not circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert circuit_breaker.is_half_open
    
    @pytest.mark.asyncio
    async def test_successful_call_closed_state(self, circuit_breaker):
        """Test successful call in closed state."""
        mock_func = AsyncMock(return_value="success")
        
        result = await circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert circuit_breaker.metrics.success_count == 1
        assert circuit_breaker.metrics.total_successes == 1
        assert circuit_breaker.metrics.total_calls == 1
        assert circuit_breaker.is_closed
        mock_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_function_call(self, circuit_breaker):
        """Test circuit breaker with synchronous function."""
        def sync_func():
            return "sync_success"
        
        result = await circuit_breaker.call(sync_func)
        
        assert result == "sync_success"
        assert circuit_breaker.metrics.success_count == 1
        assert circuit_breaker.is_closed
    
    @pytest.mark.asyncio
    async def test_failure_count_increases(self, circuit_breaker):
        """Test failure count increases with monitored exceptions."""
        mock_func = AsyncMock(side_effect=ExternalServiceError(
            code="TEST_ERROR",
            message="Service unavailable"
        ))
        
        with pytest.raises(ExternalServiceError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.metrics.failure_count == 1
        assert circuit_breaker.metrics.total_failures == 1
        assert circuit_breaker.metrics.total_calls == 1
        assert circuit_breaker.is_closed  # Still closed, threshold is 3
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, circuit_breaker):
        """Test circuit breaker opens after reaching failure threshold."""
        mock_func = AsyncMock(side_effect=ExternalServiceError(
            code="TEST_ERROR",
            message="Service unavailable"
        ))
        
        # Fail 3 times to reach threshold
        for _ in range(3):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.is_open
        assert circuit_breaker.metrics.failure_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_fails_fast_when_open(self, circuit_breaker):
        """Test circuit breaker fails fast when in open state."""
        # Force circuit to open state
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.metrics.last_failure_time = time.time()
        
        mock_func = AsyncMock(return_value="success")
        
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(mock_func)
        
        # Function should not have been called
        mock_func.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit breaker transitions to half-open after timeout."""
        # Set circuit to open state with old failure time
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.metrics.last_failure_time = time.time() - 120  # 2 minutes ago
        
        mock_func = AsyncMock(return_value="success")
        
        result = await circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert circuit_breaker.is_closed  # Should transition to closed after success
        mock_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self, circuit_breaker):
        """Test successful calls in half-open state close the circuit."""
        # Set to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        mock_func = AsyncMock(return_value="success")
        
        # Need 2 successes to close (success_threshold=2)
        await circuit_breaker.call(mock_func)
        assert circuit_breaker.is_half_open
        
        await circuit_breaker.call(mock_func)
        assert circuit_breaker.is_closed
        
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self, circuit_breaker):
        """Test failure in half-open state reopens the circuit."""
        # Set to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        mock_func = AsyncMock(side_effect=ExternalServiceError(
            code="TEST_ERROR",
            message="Still failing"
        ))
        
        with pytest.raises(ExternalServiceError):
            await circuit_breaker.call(mock_func)
        
        assert circuit_breaker.is_open
    
    @pytest.mark.asyncio
    async def test_non_monitored_exceptions_not_counted(self, circuit_breaker):
        """Test that non-monitored exceptions don't affect circuit breaker."""
        mock_func = AsyncMock(side_effect=ValueError("Not a monitored exception"))
        
        with pytest.raises(ValueError):
            await circuit_breaker.call(mock_func)
        
        # Should not affect failure count
        assert circuit_breaker.metrics.failure_count == 0
        assert circuit_breaker.is_closed
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test circuit breaker timeout handling."""
        config = CircuitBreakerConfig(timeout_duration=0.1)
        circuit_breaker = CircuitBreaker("test_timeout", config)
        
        async def slow_func():
            await asyncio.sleep(0.2)
            return "too_slow"
        
        with pytest.raises(ExternalServiceError) as exc_info:
            await circuit_breaker.call(slow_func)
        
        assert "timeout" in exc_info.value.message.lower()
        assert circuit_breaker.metrics.failure_count == 1
    
    def test_get_metrics(self, circuit_breaker):
        """Test circuit breaker metrics retrieval."""
        circuit_breaker.metrics.total_calls = 10
        circuit_breaker.metrics.total_failures = 3
        circuit_breaker.metrics.total_successes = 7
        
        metrics = circuit_breaker.get_metrics()
        
        assert metrics["name"] == "test_service"
        assert metrics["state"] == "closed"
        assert metrics["total_calls"] == 10
        assert metrics["total_failures"] == 3
        assert metrics["total_successes"] == 7
        assert metrics["failure_rate"] == 0.3
    
    def test_get_metrics_no_calls(self, circuit_breaker):
        """Test metrics with no calls made."""
        metrics = circuit_breaker.get_metrics()
        
        assert metrics["failure_rate"] == 0.0
        assert metrics["total_calls"] == 0


class TestCircuitBreakerManager:
    """Tests for CircuitBreakerManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create circuit breaker manager for testing."""
        return CircuitBreakerManager()
    
    def test_manager_get_circuit_breaker(self, manager):
        """Test getting circuit breaker from manager."""
        cb = manager.get_circuit_breaker("service1")
        
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "service1"
        assert "service1" in manager.circuit_breakers
    
    def test_manager_reuses_circuit_breaker(self, manager):
        """Test manager reuses existing circuit breaker."""
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service1")
        
        assert cb1 is cb2
        assert len(manager.circuit_breakers) == 1
    
    def test_manager_custom_config(self, manager):
        """Test creating circuit breaker with custom config."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = manager.get_circuit_breaker("service1", config)
        
        assert cb.config.failure_threshold == 10
    
    @pytest.mark.asyncio
    async def test_manager_call_with_circuit_breaker(self, manager):
        """Test manager call_with_circuit_breaker method."""
        mock_func = AsyncMock(return_value="result")
        
        result = await manager.call_with_circuit_breaker(
            "service1",
            mock_func,
            "arg1",
            kwarg1="value1"
        )
        
        assert result == "result"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        assert "service1" in manager.circuit_breakers
    
    def test_manager_get_all_metrics(self, manager):
        """Test getting all metrics from manager."""
        # Create multiple circuit breakers
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service2")
        
        # Update some metrics
        cb1.metrics.total_calls = 5
        cb2.metrics.total_calls = 3
        
        all_metrics = manager.get_all_metrics()
        
        assert "service1" in all_metrics
        assert "service2" in all_metrics
        assert all_metrics["service1"]["total_calls"] == 5
        assert all_metrics["service2"]["total_calls"] == 3
    
    def test_manager_reset_circuit_breaker(self, manager):
        """Test resetting circuit breaker state."""
        cb = manager.get_circuit_breaker("service1")
        
        # Simulate some activity
        cb.state = CircuitBreakerState.OPEN
        cb.metrics.failure_count = 5
        cb.metrics.total_calls = 10
        
        manager.reset_circuit_breaker("service1")
        
        assert cb.is_closed
        assert cb.metrics.failure_count == 0
        assert cb.metrics.total_calls == 0
    
    def test_manager_remove_circuit_breaker(self, manager):
        """Test removing circuit breaker from manager."""
        manager.get_circuit_breaker("service1")
        assert "service1" in manager.circuit_breakers
        
        manager.remove_circuit_breaker("service1")
        assert "service1" not in manager.circuit_breakers
    
    def test_manager_remove_nonexistent_circuit_breaker(self, manager):
        """Test removing non-existent circuit breaker doesn't error."""
        # Should not raise an exception
        manager.remove_circuit_breaker("nonexistent")


class TestCircuitBreakerDecorator:
    """Tests for circuit breaker decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_basic_usage(self):
        """Test basic circuit breaker decorator usage."""
        @circuit_breaker("test_service", failure_threshold=2)
        async def test_function():
            return "decorated_result"
        
        result = await test_function()
        assert result == "decorated_result"
    
    @pytest.mark.asyncio
    async def test_decorator_with_failures(self):
        """Test decorator handles failures correctly."""
        call_count = 0
        
        @circuit_breaker("failing_service", failure_threshold=2)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceError(code="TEST", message="Service down")
            return "finally_works"
        
        # First two calls should fail
        with pytest.raises(ExternalServiceError):
            await failing_function()
        
        with pytest.raises(ExternalServiceError):
            await failing_function()
        
        # Circuit should be open now
        with pytest.raises(CircuitBreakerOpenError):
            await failing_function()
    
    @pytest.mark.asyncio
    async def test_decorator_timeout(self):
        """Test decorator timeout functionality."""
        @circuit_breaker("slow_service", timeout_duration=0.1)
        async def slow_function():
            await asyncio.sleep(0.2)
            return "too_slow"
        
        with pytest.raises(ExternalServiceError) as exc_info:
            await slow_function()
        
        assert "timeout" in exc_info.value.message.lower()


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_multiple_services_isolation(self):
        """Test that different services have isolated circuit breakers."""
        manager = CircuitBreakerManager()
        
        # Mock functions for different services
        service1_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Service 1 down"))
        service2_func = AsyncMock(return_value="Service 2 OK")
        
        config = CircuitBreakerConfig(failure_threshold=1)
        
        # Service 1 fails and opens circuit
        with pytest.raises(ExternalServiceError):
            await manager.call_with_circuit_breaker("service1", service1_func, config=config)
        
        # Service 2 should still work normally
        result = await manager.call_with_circuit_breaker("service2", service2_func, config=config)
        assert result == "Service 2 OK"
        
        # Verify isolation
        cb1 = manager.get_circuit_breaker("service1")
        cb2 = manager.get_circuit_breaker("service2")
        
        assert cb1.is_open
        assert cb2.is_closed
    
    @pytest.mark.asyncio
    async def test_recovery_after_service_restoration(self):
        """Test circuit breaker recovery after service is restored."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Very short for testing
            success_threshold=1
        )
        
        circuit_breaker = CircuitBreaker("recovery_test", config)
        
        # Simulate service failures
        failing_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Down"))
        
        # Fail enough times to open circuit
        for _ in range(2):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.is_open
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Service is now working
        working_func = AsyncMock(return_value="Service restored")
        result = await circuit_breaker.call(working_func)
        
        assert result == "Service restored"
        assert circuit_breaker.is_closed
    
    @pytest.mark.asyncio
    async def test_concurrent_calls_during_half_open(self):
        """Test concurrent calls during half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=2
        )
        
        circuit_breaker = CircuitBreaker("concurrent_test", config)
        
        # Open the circuit
        failing_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Down"))
        with pytest.raises(ExternalServiceError):
            await circuit_breaker.call(failing_func)
        
        assert circuit_breaker.is_open
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Multiple concurrent calls during half-open
        working_func = AsyncMock(return_value="OK")
        
        # First call should succeed and transition to closed
        result = await circuit_breaker.call(working_func)
        assert result == "OK"
        
        # Subsequent calls should also work since circuit is now closed
        result2 = await circuit_breaker.call(working_func)
        assert result2 == "OK"
    
    def test_global_circuit_breaker_manager(self):
        """Test global circuit breaker manager singleton."""
        manager1 = get_circuit_breaker_manager()
        manager2 = get_circuit_breaker_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, CircuitBreakerManager)


class TestCircuitBreakerErrorScenarios:
    """Tests for various error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_correlation_id(self):
        """Test circuit breaker call with correlation ID."""
        circuit_breaker = CircuitBreaker("test_service")
        mock_func = AsyncMock(return_value="success")
        
        result = await circuit_breaker.call(
            mock_func, 
            correlation_id="test-correlation-123"
        )
        
        assert result == "success"
        mock_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions_logging(self, caplog):
        """Test that state transitions are logged."""
        config = CircuitBreakerConfig(failure_threshold=1)
        circuit_breaker = CircuitBreaker("logging_test", config)
        
        # Trigger state transition
        failing_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Service down"))
        
        with pytest.raises(ExternalServiceError):
            await circuit_breaker.call(failing_func)
        
        # Check that state transition was logged
        assert any("state transition" in record.message.lower() for record in caplog.records)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics_accuracy(self):
        """Test accuracy of circuit breaker metrics."""
        circuit_breaker = CircuitBreaker("metrics_test")
        
        # Mix of successful and failed calls
        success_func = AsyncMock(return_value="OK")
        fail_func = AsyncMock(side_effect=ExternalServiceError(code="ERROR", message="Fail"))
        
        # 3 successes
        for _ in range(3):
            await circuit_breaker.call(success_func)
        
        # 2 failures
        for _ in range(2):
            with pytest.raises(ExternalServiceError):
                await circuit_breaker.call(fail_func)
        
        metrics = circuit_breaker.get_metrics()
        
        assert metrics["total_calls"] == 5
        assert metrics["total_successes"] == 3
        assert metrics["total_failures"] == 2
        assert metrics["failure_rate"] == 0.4
        assert metrics["success_count"] == 0  # Reset after failures
        assert metrics["failure_count"] == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_exception_preservation(self):
        """Test that original exceptions are preserved."""
        circuit_breaker = CircuitBreaker("exception_test")
        
        original_error = GoogleNewsUnavailableError(
            "Google News is down",
            {"status_code": 503, "retry_after": 300}
        )
        
        mock_func = AsyncMock(side_effect=original_error)
        
        with pytest.raises(GoogleNewsUnavailableError) as exc_info:
            await circuit_breaker.call(mock_func)
        
        # Should be the same exception instance
        assert exc_info.value is original_error
        assert exc_info.value.details["status_code"] == 503