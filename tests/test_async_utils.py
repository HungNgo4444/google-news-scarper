"""Tests for async utilities module.

This test suite covers all functionality in src.shared.async_utils,
including event loop detection, safe async execution, and Celery integration.
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from src.shared.async_utils import (
    AsyncExecutionError,
    safe_async_run,
    celery_safe_async,
    sync_to_async_safe,
    ensure_async_context,
    AsyncContextManager,
    get_event_loop_info,
    is_event_loop_running,
    is_in_async_context,
    run_in_executor,
    _run_async_new_loop,
    _run_async_in_thread
)


class TestEventLoopDetection:
    """Test event loop detection functions."""

    def test_get_event_loop_info_no_loop(self):
        """Test getting event loop info when no loop is running."""
        info = get_event_loop_info()

        assert info["has_running_loop"] is False
        assert info["loop_running"] is False
        assert info["loop_closed"] is None
        assert info["thread_id"] == threading.get_ident()
        assert info["loop_debug"] is None

    @pytest.mark.asyncio
    async def test_get_event_loop_info_with_loop(self):
        """Test getting event loop info when loop is running."""
        info = get_event_loop_info()

        assert info["has_running_loop"] is True
        assert info["loop_running"] is True
        assert info["loop_closed"] is False
        assert info["thread_id"] == threading.get_ident()
        assert isinstance(info["loop_debug"], bool)

    def test_is_event_loop_running_no_loop(self):
        """Test is_event_loop_running when no loop exists."""
        assert is_event_loop_running() is False

    @pytest.mark.asyncio
    async def test_is_event_loop_running_with_loop(self):
        """Test is_event_loop_running when loop exists."""
        assert is_event_loop_running() is True

    def test_is_in_async_context_no_loop(self):
        """Test is_in_async_context when no loop exists."""
        assert is_in_async_context() is False

    @pytest.mark.asyncio
    async def test_is_in_async_context_with_loop(self):
        """Test is_in_async_context when loop exists."""
        assert is_in_async_context() is True


class TestSafeAsyncRun:
    """Test safe_async_run function."""

    async def simple_async_func(self, value: int) -> int:
        """Simple async function for testing."""
        await asyncio.sleep(0.01)  # Small delay
        return value * 2

    async def failing_async_func(self, error_msg: str):
        """Async function that raises an exception."""
        await asyncio.sleep(0.01)
        raise ValueError(error_msg)

    async def timeout_async_func(self, delay: float):
        """Async function that takes longer than timeout."""
        await asyncio.sleep(delay)
        return "completed"

    def test_safe_async_run_no_loop(self):
        """Test safe_async_run when no event loop is running."""
        coro = self.simple_async_func(5)
        result = safe_async_run(coro)

        assert result == 10

    def test_safe_async_run_with_timeout(self):
        """Test safe_async_run with timeout."""
        coro = self.simple_async_func(3)
        result = safe_async_run(coro, timeout=1.0)

        assert result == 6

    def test_safe_async_run_timeout_error(self):
        """Test safe_async_run when timeout is exceeded."""
        coro = self.timeout_async_func(2.0)

        with pytest.raises(AsyncExecutionError):
            safe_async_run(coro, timeout=0.1)

    def test_safe_async_run_with_fallback(self):
        """Test safe_async_run with fallback result."""
        coro = self.failing_async_func("test error")
        result = safe_async_run(coro, fallback_result="fallback")

        assert result == "fallback"

    def test_safe_async_run_error_no_fallback(self):
        """Test safe_async_run raises error when no fallback provided."""
        coro = self.failing_async_func("test error")

        with pytest.raises(AsyncExecutionError) as exc_info:
            safe_async_run(coro)

        assert "Safe async execution failed" in str(exc_info.value)
        assert isinstance(exc_info.value.original_error, ValueError)

    @pytest.mark.asyncio
    async def test_safe_async_run_in_async_context(self):
        """Test safe_async_run when called from async context."""
        # This should run in a separate thread
        coro = self.simple_async_func(7)
        result = safe_async_run(coro)

        assert result == 14

    def test_safe_async_run_correlation_id(self):
        """Test safe_async_run with correlation ID tracking."""
        coro = self.simple_async_func(4)
        coro.__correlation_id__ = "test-123"

        result = safe_async_run(coro)
        assert result == 8


class TestCelerySafeAsync:
    """Test celery_safe_async decorator."""

    def test_celery_safe_async_decorator(self):
        """Test basic celery_safe_async decorator functionality."""

        @celery_safe_async(timeout=5, fallback_result=0)
        async def test_async_func(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 3

        result = test_async_func(4)
        assert result == 12

    def test_celery_safe_async_with_error(self):
        """Test celery_safe_async decorator with error and fallback."""

        @celery_safe_async(timeout=5, fallback_result=-1)
        async def failing_func():
            raise ValueError("Test error")

        result = failing_func()
        assert result == -1

    def test_celery_safe_async_with_retry(self):
        """Test celery_safe_async decorator with retry functionality."""
        call_count = 0

        @celery_safe_async(retry_on_failure=True, fallback_result=None)
        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return "success"

        with pytest.raises(AsyncExecutionError):
            intermittent_func()

        # Should have been called twice (original + retry)
        assert call_count == 2

    def test_celery_safe_async_timeout(self):
        """Test celery_safe_async decorator with timeout."""

        @celery_safe_async(timeout=0.1, fallback_result="timeout")
        async def slow_func():
            await asyncio.sleep(1.0)
            return "completed"

        result = slow_func()
        assert result == "timeout"

    def test_celery_safe_async_with_mock_celery_task(self):
        """Test celery_safe_async decorator with mock Celery task context."""

        # Mock Celery task context
        mock_request = Mock()
        mock_request.id = "task-123"

        @celery_safe_async(timeout=5)
        async def task_func(self, value: int) -> int:
            return value * 2

        # Simulate Celery task context
        task_func.__self__ = Mock()
        task_func.__self__.request = mock_request

        result = task_func(None, 5)
        assert result == 10


class TestAsyncContextManager:
    """Test AsyncContextManager class."""

    @pytest.mark.asyncio
    async def test_async_context_manager_success(self):
        """Test AsyncContextManager with successful execution."""
        async with AsyncContextManager(timeout=5) as ctx:
            result = await ctx.safe_execute(self._simple_async(10))

        assert result == 20

    @pytest.mark.asyncio
    async def test_async_context_manager_timeout(self):
        """Test AsyncContextManager with timeout."""
        with pytest.raises(asyncio.TimeoutError):
            async with AsyncContextManager(timeout=0.1) as ctx:
                await ctx.safe_execute(self._slow_async())

    @pytest.mark.asyncio
    async def test_async_context_manager_error(self):
        """Test AsyncContextManager with error."""
        with pytest.raises(ValueError):
            async with AsyncContextManager(timeout=5) as ctx:
                await ctx.safe_execute(self._failing_async())

    async def _simple_async(self, value: int) -> int:
        """Helper async function."""
        await asyncio.sleep(0.01)
        return value * 2

    async def _slow_async(self) -> str:
        """Helper slow async function."""
        await asyncio.sleep(1.0)
        return "completed"

    async def _failing_async(self):
        """Helper failing async function."""
        raise ValueError("Test error")


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_run_in_executor(self):
        """Test run_in_executor function."""
        def sync_func(a: int, b: int) -> int:
            return a + b

        result = await run_in_executor(sync_func, 5, 10)
        assert result == 15

    @pytest.mark.asyncio
    async def test_run_in_executor_with_kwargs(self):
        """Test run_in_executor with keyword arguments."""
        def sync_func(a: int, b: int = 10) -> int:
            return a * b

        result = await run_in_executor(sync_func, 3, b=4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_run_in_executor_custom_executor(self):
        """Test run_in_executor with custom executor."""
        def sync_func(value: int) -> int:
            return value ** 2

        with ThreadPoolExecutor(max_workers=2) as executor:
            result = await run_in_executor(sync_func, 6, executor=executor)

        assert result == 36

    def test_sync_to_async_safe(self):
        """Test sync_to_async_safe conversion."""
        def sync_func(x: int, y: int) -> int:
            return x * y

        async_func = sync_to_async_safe(sync_func)

        # Test in async context
        async def test_wrapper():
            return await async_func(4, 5)

        result = safe_async_run(test_wrapper())
        assert result == 20

    def test_ensure_async_context(self):
        """Test ensure_async_context decorator."""

        @ensure_async_context
        async def async_func(value: int) -> int:
            await asyncio.sleep(0.01)
            return value ** 2

        # Should work in sync context
        result = async_func(7)
        assert result == 49


class TestInternalFunctions:
    """Test internal helper functions."""

    def test_run_async_new_loop(self):
        """Test _run_async_new_loop function."""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "success"

        result = _run_async_new_loop(test_coro())
        assert result == "success"

    def test_run_async_new_loop_with_timeout(self):
        """Test _run_async_new_loop with timeout."""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "success"

        result = _run_async_new_loop(test_coro(), timeout=1.0)
        assert result == "success"

    def test_run_async_in_thread(self):
        """Test _run_async_in_thread function."""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "thread_success"

        result = _run_async_in_thread(test_coro())
        assert result == "thread_success"

    def test_run_async_in_thread_with_timeout(self):
        """Test _run_async_in_thread with timeout."""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "thread_timeout_success"

        result = _run_async_in_thread(test_coro(), timeout=1.0)
        assert result == "thread_timeout_success"


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_async_execution_error_creation(self):
        """Test AsyncExecutionError creation."""
        original_error = ValueError("Original error")
        async_error = AsyncExecutionError("Async failed", original_error)

        assert async_error.message == "Async failed"
        assert async_error.original_error is original_error
        assert str(async_error) == "Async failed"

    def test_async_execution_error_without_original(self):
        """Test AsyncExecutionError without original error."""
        async_error = AsyncExecutionError("Simple async error")

        assert async_error.message == "Simple async error"
        assert async_error.original_error is None


class TestConcurrency:
    """Test concurrent execution scenarios."""

    def test_multiple_concurrent_safe_async_run(self):
        """Test multiple concurrent safe_async_run calls."""
        async def async_task(task_id: int, delay: float) -> str:
            await asyncio.sleep(delay)
            return f"task_{task_id}_completed"

        # Run multiple tasks concurrently
        import concurrent.futures

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(
                    safe_async_run,
                    async_task(i, 0.05)
                )
                futures.append(future)

            results = [f.result() for f in futures]

        assert len(results) == 3
        assert all("completed" in result for result in results)

    @pytest.mark.asyncio
    async def test_nested_async_context(self):
        """Test nested async context handling."""
        async def inner_async(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2

        async def outer_async(value: int) -> int:
            # This should work even though we're in async context
            result = safe_async_run(inner_async(value))
            return result + 1

        result = await outer_async(5)
        assert result == 11


# Integration test fixtures
@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    task = Mock()
    task.request = Mock()
    task.request.id = "test-task-123"
    return task


# Performance tests
class TestPerformance:
    """Test performance characteristics."""

    def test_safe_async_run_performance(self):
        """Test performance of safe_async_run."""
        async def quick_task(value: int) -> int:
            return value * 2

        start_time = time.time()
        for i in range(10):
            safe_async_run(quick_task(i))
        end_time = time.time()

        # Should complete reasonably quickly
        assert (end_time - start_time) < 1.0

    def test_event_loop_detection_performance(self):
        """Test performance of event loop detection."""
        start_time = time.time()
        for _ in range(1000):
            is_event_loop_running()
            is_in_async_context()
        end_time = time.time()

        # Should be very fast
        assert (end_time - start_time) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])