"""Circuit breaker pattern implementation for external service protection."""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, Union
from dataclasses import dataclass, field
import logging

from src.shared.exceptions import BaseAppException, ExternalServiceError, ErrorCode

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5              # Failures before opening circuit
    recovery_timeout: int = 300             # Seconds before trying half-open (5 minutes)
    success_threshold: int = 3              # Successes in half-open before closing
    timeout_duration: Optional[int] = None  # Timeout for individual calls (seconds)
    monitored_exceptions: tuple = (ExternalServiceError,)


@dataclass
class CircuitBreakerMetrics:
    """Metrics tracked by circuit breaker."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_change_time: float = field(default_factory=time.time)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreakerOpenError(BaseAppException):
    """Raised when circuit breaker is open and calls are rejected."""
    
    def __init__(self, service_name: str, next_retry_time: float):
        message = f"Circuit breaker open for {service_name}, retry after {time.ctime(next_retry_time)}"
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
            message=message,
            details={
                "service_name": service_name,
                "next_retry_time": next_retry_time,
                "circuit_breaker_state": "open"
            },
            retryable=True,
            retry_after=int(next_retry_time - time.time())
        )


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (normal operation)."""
        return self.state == CircuitBreakerState.CLOSED
    
    @property 
    def is_open(self) -> bool:
        """Check if circuit breaker is open (failing fast)."""
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open (testing recovery)."""
        return self.state == CircuitBreakerState.HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset from open to half-open."""
        if self.state != CircuitBreakerState.OPEN:
            return False
        
        if not self.metrics.last_failure_time:
            return False
        
        time_since_failure = time.time() - self.metrics.last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    async def _transition_state(self, new_state: CircuitBreakerState, reason: str):
        """Transition circuit breaker to a new state."""
        old_state = self.state
        self.state = new_state
        self.metrics.state_change_time = time.time()
        
        logger.info(
            f"Circuit breaker {self.name} state transition: {old_state.value} -> {new_state.value}",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason,
                "failure_count": self.metrics.failure_count,
                "success_count": self.metrics.success_count
            }
        )
        
        # Reset counters on state change
        if new_state == CircuitBreakerState.CLOSED:
            self.metrics.failure_count = 0
            self.metrics.success_count = 0
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self.metrics.success_count = 0
    
    async def _record_success(self):
        """Record a successful operation."""
        async with self._lock:
            current_time = time.time()
            self.metrics.success_count += 1
            self.metrics.total_successes += 1
            self.metrics.last_success_time = current_time
            
            logger.debug(
                f"Circuit breaker {self.name} recorded success",
                extra={
                    "circuit_breaker": self.name,
                    "state": self.state.value,
                    "success_count": self.metrics.success_count,
                    "total_successes": self.metrics.total_successes
                }
            )
            
            # Transition from half-open to closed if enough successes
            if (self.state == CircuitBreakerState.HALF_OPEN and 
                self.metrics.success_count >= self.config.success_threshold):
                await self._transition_state(
                    CircuitBreakerState.CLOSED,
                    f"Reached success threshold ({self.config.success_threshold})"
                )
    
    async def _record_failure(self, exception: Exception):
        """Record a failed operation."""
        async with self._lock:
            current_time = time.time()
            self.metrics.failure_count += 1
            self.metrics.total_failures += 1
            self.metrics.last_failure_time = current_time
            
            logger.warning(
                f"Circuit breaker {self.name} recorded failure: {exception}",
                extra={
                    "circuit_breaker": self.name,
                    "state": self.state.value,
                    "failure_count": self.metrics.failure_count,
                    "total_failures": self.metrics.total_failures,
                    "error": str(exception),
                    "error_type": type(exception).__name__
                }
            )
            
            # Transition to open if failure threshold reached
            if (self.state == CircuitBreakerState.CLOSED and 
                self.metrics.failure_count >= self.config.failure_threshold):
                await self._transition_state(
                    CircuitBreakerState.OPEN,
                    f"Reached failure threshold ({self.config.failure_threshold})"
                )
            
            # From half-open back to open on any failure
            elif self.state == CircuitBreakerState.HALF_OPEN:
                await self._transition_state(
                    CircuitBreakerState.OPEN,
                    "Failure during half-open state"
                )
    
    def _should_monitor_exception(self, exception: Exception) -> bool:
        """Check if this exception should be monitored by the circuit breaker."""
        return isinstance(exception, self.config.monitored_exceptions)
    
    async def call(self, func: Callable, *args, correlation_id: Optional[str] = None, **kwargs) -> Any:
        """Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute (sync or async)
            *args: Arguments for the function
            correlation_id: Correlation ID for logging
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception: If function fails and circuit should remain closed
        """
        # Increment total calls
        self.metrics.total_calls += 1
        
        # Check if we should attempt reset from open state
        if self.is_open and self._should_attempt_reset():
            async with self._lock:
                if self.is_open and self._should_attempt_reset():  # Double-check with lock
                    await self._transition_state(CircuitBreakerState.HALF_OPEN, "Recovery timeout reached")
        
        # Fail fast if circuit is open
        if self.is_open:
            next_retry_time = (self.metrics.last_failure_time or time.time()) + self.config.recovery_timeout
            logger.warning(
                f"Circuit breaker {self.name} is open, failing fast",
                extra={
                    "circuit_breaker": self.name,
                    "correlation_id": correlation_id,
                    "next_retry_time": time.ctime(next_retry_time)
                }
            )
            raise CircuitBreakerOpenError(self.name, next_retry_time)
        
        # Allow only one call in half-open state
        if self.is_half_open:
            async with self._lock:
                if self.metrics.success_count > 0:
                    # Another call succeeded, let it through
                    pass
                elif self.metrics.failure_count > 0:
                    # Another call failed, circuit should be open
                    next_retry_time = time.time() + self.config.recovery_timeout
                    raise CircuitBreakerOpenError(self.name, next_retry_time)
        
        # Execute the function
        try:
            logger.debug(
                f"Circuit breaker {self.name} executing call to {func.__name__}",
                extra={
                    "circuit_breaker": self.name,
                    "correlation_id": correlation_id,
                    "function": func.__name__,
                    "state": self.state.value
                }
            )
            
            # Handle timeout if configured
            if self.config.timeout_duration:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.config.timeout_duration
                    )
                else:
                    # For sync functions, we can't easily implement timeout without threading
                    result = func(*args, **kwargs)
            else:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            
            # Record success
            await self._record_success()
            return result
            
        except asyncio.TimeoutError as e:
            # Timeout is considered a monitored failure
            timeout_error = ExternalServiceError(
                code=ErrorCode.EXTRACTION_TIMEOUT,
                message=f"Circuit breaker timeout ({self.config.timeout_duration}s) for {self.name}",
                details={
                    "circuit_breaker": self.name,
                    "timeout": self.config.timeout_duration,
                    "function": func.__name__
                }
            )
            await self._record_failure(timeout_error)
            raise timeout_error
            
        except Exception as e:
            # Record failure only for monitored exceptions
            if self._should_monitor_exception(e):
                await self._record_failure(e)
            else:
                logger.debug(
                    f"Circuit breaker {self.name} not monitoring exception {type(e).__name__}",
                    extra={
                        "circuit_breaker": self.name,
                        "correlation_id": correlation_id,
                        "error_type": type(e).__name__
                    }
                )
            raise e
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "total_calls": self.metrics.total_calls,
            "total_failures": self.metrics.total_failures,
            "total_successes": self.metrics.total_successes,
            "last_failure_time": self.metrics.last_failure_time,
            "last_success_time": self.metrics.last_success_time,
            "state_change_time": self.metrics.state_change_time,
            "failure_rate": (
                self.metrics.total_failures / self.metrics.total_calls 
                if self.metrics.total_calls > 0 else 0.0
            )
        }


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different services."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config or self.default_config)
            logger.info(f"Created circuit breaker for service: {name}")
        
        return self.circuit_breakers[name]
    
    async def call_with_circuit_breaker(
        self,
        service_name: str,
        func: Callable,
        *args,
        config: Optional[CircuitBreakerConfig] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection.
        
        Args:
            service_name: Name of the service for circuit breaker identification
            func: Function to execute
            *args: Arguments for the function
            config: Optional circuit breaker configuration
            correlation_id: Correlation ID for logging
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
        """
        circuit_breaker = self.get_circuit_breaker(service_name, config)
        return await circuit_breaker.call(func, *args, correlation_id=correlation_id, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()}
    
    def reset_circuit_breaker(self, service_name: str):
        """Reset a circuit breaker to closed state."""
        if service_name in self.circuit_breakers:
            cb = self.circuit_breakers[service_name]
            cb.state = CircuitBreakerState.CLOSED
            cb.metrics = CircuitBreakerMetrics()
            logger.info(f"Reset circuit breaker for service: {service_name}")
    
    def remove_circuit_breaker(self, service_name: str):
        """Remove a circuit breaker."""
        if service_name in self.circuit_breakers:
            del self.circuit_breakers[service_name]
            logger.info(f"Removed circuit breaker for service: {service_name}")


# Global circuit breaker manager instance
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager instance."""
    return _circuit_breaker_manager


# Convenience decorator
def circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 300,
    success_threshold: int = 3,
    timeout_duration: Optional[int] = None
):
    """Decorator for applying circuit breaker to functions.
    
    Args:
        service_name: Name of the service for circuit breaker identification
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        success_threshold: Successes needed in half-open before closing
        timeout_duration: Timeout for individual calls
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            config = CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                success_threshold=success_threshold,
                timeout_duration=timeout_duration
            )
            
            manager = get_circuit_breaker_manager()
            return await manager.call_with_circuit_breaker(
                service_name, func, *args, config=config, **kwargs
            )
        
        return wrapper
    return decorator