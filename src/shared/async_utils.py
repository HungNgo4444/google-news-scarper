"""Async utilities for safe execution in different contexts.

This module provides utilities for handling async/sync boundaries safely,
particularly in Celery worker contexts where event loops may already exist.

Key Features:
- Safe async execution in Celery workers
- Event loop detection and management
- Compatibility layer for different execution contexts
- Graceful fallback mechanisms
"""

import asyncio
import functools
import logging
import threading
from typing import Any, Awaitable, Callable, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class AsyncExecutionError(Exception):
    """Exception raised when async execution fails."""

    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


def get_event_loop_info() -> dict[str, Any]:
    """Get information about the current event loop state.

    Returns:
        dict: Information about event loop status
    """
    try:
        loop = asyncio.get_running_loop()
        return {
            "has_running_loop": True,
            "loop_running": loop.is_running(),
            "loop_closed": loop.is_closed(),
            "thread_id": threading.get_ident(),
            "loop_debug": loop.get_debug()
        }
    except RuntimeError:
        return {
            "has_running_loop": False,
            "loop_running": False,
            "loop_closed": None,
            "thread_id": threading.get_ident(),
            "loop_debug": None
        }


def is_event_loop_running() -> bool:
    """Check if an event loop is currently running.

    Returns:
        bool: True if event loop is running, False otherwise
    """
    try:
        loop = asyncio.get_running_loop()
        return loop.is_running()
    except RuntimeError:
        return False


def is_in_async_context() -> bool:
    """Check if we're currently in an async context.

    Returns:
        bool: True if in async context, False otherwise
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


async def run_in_executor(
    func: Callable[..., T],
    *args,
    executor: ThreadPoolExecutor = None,
    **kwargs
) -> T:
    """Run a sync function in an executor from async context.

    Args:
        func: Synchronous function to execute
        *args: Positional arguments for the function
        executor: Optional executor to use
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function execution
    """
    loop = asyncio.get_running_loop()

    # Create a partial function with kwargs if needed
    if kwargs:
        partial_func = functools.partial(func, **kwargs)
        return await loop.run_in_executor(executor, partial_func, *args)
    else:
        return await loop.run_in_executor(executor, func, *args)


def safe_async_run(
    coro: Awaitable[T],
    timeout: float = None,
    fallback_result: T = None
) -> T:
    """Safely run an async coroutine in various contexts.

    This function handles:
    - Running in new event loop if none exists
    - Running in thread if event loop already exists
    - Graceful error handling with fallback

    Args:
        coro: Coroutine to execute
        timeout: Optional timeout in seconds
        fallback_result: Result to return if execution fails

    Returns:
        Result of coroutine execution or fallback_result

    Raises:
        AsyncExecutionError: If execution fails and no fallback provided
    """
    correlation_id = getattr(coro, '__correlation_id__', 'unknown')

    logger.info(
        "Starting safe async execution",
        correlation_id=correlation_id,
        has_running_loop=is_event_loop_running(),
        thread_id=threading.get_ident()
    )

    try:
        # Check if we're already in an async context
        if is_event_loop_running():
            # We're in an existing event loop - run in thread
            logger.debug(
                "Event loop detected, running in thread executor",
                correlation_id=correlation_id
            )
            return _run_async_in_thread(coro, timeout)
        else:
            # No event loop - create new one
            logger.debug(
                "No event loop detected, creating new one",
                correlation_id=correlation_id
            )
            return _run_async_new_loop(coro, timeout)

    except Exception as e:
        logger.error(
            "Async execution failed",
            correlation_id=correlation_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )

        if fallback_result is not None:
            logger.warning(
                "Using fallback result due to execution failure",
                correlation_id=correlation_id,
                fallback_result=fallback_result
            )
            return fallback_result

        raise AsyncExecutionError(
            f"Safe async execution failed: {str(e)}",
            original_error=e
        )


def _run_async_new_loop(coro: Awaitable[T], timeout: float = None) -> T:
    """Run coroutine in a new event loop.

    Args:
        coro: Coroutine to execute
        timeout: Optional timeout in seconds

    Returns:
        Result of coroutine execution
    """
    if timeout:
        # Wrap with timeout
        async def _with_timeout():
            return await asyncio.wait_for(coro, timeout=timeout)
        return asyncio.run(_with_timeout())
    else:
        return asyncio.run(coro)


def _run_async_in_thread(coro: Awaitable[T], timeout: float = None) -> T:
    """Run coroutine in a separate thread with new event loop.

    Args:
        coro: Coroutine to execute
        timeout: Optional timeout in seconds

    Returns:
        Result of coroutine execution
    """
    import concurrent.futures

    def _thread_runner():
        # Create new event loop for this thread
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        try:
            if timeout:
                async def _with_timeout():
                    return await asyncio.wait_for(coro, timeout=timeout)
                return new_loop.run_until_complete(_with_timeout())
            else:
                return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_thread_runner)
        return future.result(timeout=timeout)


def celery_safe_async(
    timeout: float = 300,
    fallback_result: Any = None,
    retry_on_failure: bool = False
):
    """Decorator for making async functions safe to run in Celery tasks.

    Args:
        timeout: Execution timeout in seconds
        fallback_result: Result to return if execution fails
        retry_on_failure: Whether to retry on failure

    Usage:
        @celery_safe_async(timeout=60, fallback_result={})
        async def my_async_task():
            # async code here
            pass
    """
    def decorator(async_func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
        @functools.wraps(async_func)
        def wrapper(*args, **kwargs) -> T:
            # Create coroutine
            coro = async_func(*args, **kwargs)

            # Add correlation ID for tracking
            if hasattr(wrapper, '__self__') and hasattr(wrapper.__self__, 'request'):
                correlation_id = getattr(wrapper.__self__.request, 'id', 'unknown')
                coro.__correlation_id__ = correlation_id

            # Execute safely
            try:
                return safe_async_run(
                    coro,
                    timeout=timeout,
                    fallback_result=fallback_result
                )
            except AsyncExecutionError as e:
                if retry_on_failure:
                    logger.warning(
                        "Async execution failed, retrying",
                        error=str(e),
                        function=async_func.__name__
                    )
                    # Simple retry logic - could be enhanced
                    try:
                        coro_retry = async_func(*args, **kwargs)
                        return safe_async_run(
                            coro_retry,
                            timeout=timeout,
                            fallback_result=fallback_result
                        )
                    except Exception as retry_error:
                        logger.error(
                            "Retry also failed",
                            error=str(retry_error),
                            function=async_func.__name__
                        )
                        raise
                else:
                    raise

        return wrapper
    return decorator


def sync_to_async_safe(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """Convert sync function to async safely.

    Args:
        func: Synchronous function to convert

    Returns:
        Async version of the function
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return async_wrapper


class AsyncContextManager:
    """Context manager for safe async execution.

    Usage:
        async with AsyncContextManager() as ctx:
            result = await ctx.safe_execute(my_coroutine())
    """

    def __init__(self, timeout: float = 300):
        self.timeout = timeout
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def __aenter__(self):
        self.logger.debug("Entering async context manager")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.debug("Exiting async context manager")
        if exc_type:
            self.logger.error(
                "Exception in async context",
                exc_type=exc_type.__name__,
                exc_val=str(exc_val)
            )
        return False

    async def safe_execute(self, coro: Awaitable[T]) -> T:
        """Execute coroutine safely within context.

        Args:
            coro: Coroutine to execute

        Returns:
            Result of execution
        """
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout)
        except asyncio.TimeoutError:
            self.logger.error("Async execution timed out", timeout=self.timeout)
            raise
        except Exception as e:
            self.logger.error(
                "Async execution failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise


# Convenience functions for common patterns
def ensure_async_context(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """Ensure function can run in both sync and async contexts.

    Args:
        func: Async function to wrap

    Returns:
        Function that can run in any context
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        return safe_async_run(coro)

    return wrapper


# Export main utilities
__all__ = [
    'AsyncExecutionError',
    'safe_async_run',
    'celery_safe_async',
    'sync_to_async_safe',
    'ensure_async_context',
    'AsyncContextManager',
    'get_event_loop_info',
    'is_event_loop_running',
    'is_in_async_context',
    'run_in_executor'
]