"""Celery tasks for job scheduling and execution.

This module provides Celery tasks for background job processing including:
- Category crawling tasks with comprehensive error handling
- Job status tracking and correlation
- Maintenance and cleanup tasks
- Health monitoring tasks

All tasks follow structured logging patterns and include proper error handling,
retry logic, and status tracking through the CrawlJobRepository.

Example:
    Triggering a crawl task:
    
    ```python
    from src.core.scheduler.tasks import crawl_category_task
    
    # Schedule a category crawl
    result = crawl_category_task.delay(
        category_id="uuid-string",
        job_id="job-uuid-string"
    )
    
    # Get task status
    status = result.status
    ```
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import UUID, uuid4

from celery import current_task
from celery.utils.log import get_task_logger

from src.core.scheduler.celery_app import celery_app
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.category_repo import CategoryRepository
from src.database.repositories.article_repo import ArticleRepository
from src.core.crawler.engine import CrawlerEngine
from src.core.crawler.extractor import ArticleExtractor
from src.shared.config import get_settings
from src.shared.exceptions import (
    BaseAppException,
    ExternalServiceError,
    GoogleNewsUnavailableError,
    RateLimitExceededError,
    DatabaseConnectionError,
    CeleryTaskFailedError,
    InternalServerError
)
from src.core.error_handling.retry_handler import RetryHandler, EXTERNAL_SERVICE_RETRY
from src.core.error_handling.alert_manager import get_alert_manager, AlertType, AlertSeverity

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def crawl_category_task(self, category_id: str, job_id: str) -> Dict[str, Any]:
    """Execute crawl for specific category with comprehensive error handling.
    
    This is the main background task for crawling articles from a category.
    It includes comprehensive error handling, status tracking, and metrics collection.
    
    Args:
        category_id: UUID string of the category to crawl
        job_id: UUID string of the CrawlJob tracking this execution
        
    Returns:
        Dictionary containing execution results and metrics
        
    Raises:
        CrawlerError: For crawler-specific errors
        Exception: For general execution errors
    """
    correlation_id = f"job_{job_id}_{self.request.id}"
    settings = get_settings()
    
    logger.info("Starting crawl task", extra={
        "correlation_id": correlation_id,
        "category_id": category_id,
        "job_id": job_id,
        "task_id": self.request.id,
        "retry_count": self.request.retries
    })
    
    # Convert to async and run the crawl operation
    return asyncio.run(_async_crawl_category_task(
        self, category_id, job_id, correlation_id, settings
    ))


async def _async_crawl_category_task(
    task_instance,
    category_id: str,
    job_id: str,
    correlation_id: str,
    settings
) -> Dict[str, Any]:
    """Async implementation of the category crawl task.
    
    Args:
        task_instance: Celery task instance for retry handling
        category_id: Category UUID string
        job_id: Job UUID string
        correlation_id: Unique correlation ID for tracking
        settings: Application settings
        
    Returns:
        Task execution results
    """
    job_repo = CrawlJobRepository()
    
    try:
        # Update job status to running
        await job_repo.update_status(
            job_id=UUID(job_id),
            status="running",
            started_at=datetime.now(timezone.utc),
            celery_task_id=task_instance.request.id,
            correlation_id=correlation_id
        )
        
        # Get category and validate
        category_repo = CategoryRepository()
        category = await category_repo.get_by_id(UUID(category_id))
        
        if not category:
            error_msg = f"Category {category_id} not found"
            logger.error(error_msg, extra={"correlation_id": correlation_id})
            
            await job_repo.update_status(
                job_id=UUID(job_id),
                status="failed",
                error_message=error_msg,
                completed_at=datetime.now(timezone.utc)
            )
            return {"status": "failed", "error": error_msg}
        
        if not category.is_active:
            error_msg = f"Category {category.name} is not active"
            logger.warning(error_msg, extra={"correlation_id": correlation_id})
            
            await job_repo.update_status(
                job_id=UUID(job_id),
                status="completed",  # Not an error, just skipped
                error_message=error_msg,
                completed_at=datetime.now(timezone.utc),
                articles_found=0,
                articles_saved=0
            )
            return {"status": "skipped", "reason": error_msg}
        
        # Initialize crawler dependencies
        article_repo = ArticleRepository()
        article_extractor = ArticleExtractor(
            settings=settings,
            logger=logger
        )
        
        # Create crawler engine with job tracking
        crawler = CrawlerEngine(
            settings=settings,
            logger=logger,
            article_extractor=article_extractor,
            article_repo=article_repo
        )
        
        # Execute crawl with enhanced tracking
        articles_found, articles_saved = await _execute_crawl_with_tracking(
            crawler=crawler,
            category=category,
            job_id=UUID(job_id),
            correlation_id=correlation_id
        )
        
        # Update completion status
        await job_repo.update_status(
            job_id=UUID(job_id),
            status="completed",
            articles_found=articles_found,
            articles_saved=articles_saved,
            completed_at=datetime.now(timezone.utc)
        )
        
        logger.info("Crawl completed successfully", extra={
            "correlation_id": correlation_id,
            "category_name": category.name,
            "articles_found": articles_found,
            "articles_saved": articles_saved
        })
        
        return {
            "status": "completed",
            "category_name": category.name,
            "articles_found": articles_found,
            "articles_saved": articles_saved,
            "correlation_id": correlation_id
        }
        
    except RateLimitExceededError as e:
        return await _handle_task_error(
            task_instance=task_instance,
            exception=e,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="rate_limit"
        )
        
    except GoogleNewsUnavailableError as e:
        return await _handle_task_error(
            task_instance=task_instance,
            exception=e,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="external_service"
        )
        
    except ExternalServiceError as e:
        return await _handle_task_error(
            task_instance=task_instance,
            exception=e,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="external_service"
        )
        
    except DatabaseConnectionError as e:
        return await _handle_task_error(
            task_instance=task_instance,
            exception=e,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="database"
        )
        
    except BaseAppException as e:
        return await _handle_task_error(
            task_instance=task_instance,
            exception=e,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="application"
        )
        
    except Exception as e:
        # Wrap unexpected exceptions
        wrapped_exception = CeleryTaskFailedError(
            task_name="crawl_category_task",
            message=str(e),
            details={
                "original_error_type": type(e).__name__,
                "category_id": category_id,
                "job_id": job_id
            }
        )
        
        return await _handle_task_error(
            task_instance=task_instance,
            exception=wrapped_exception,
            job_id=UUID(job_id),
            job_repo=job_repo,
            correlation_id=correlation_id,
            error_category="unexpected"
        )


async def _execute_crawl_with_tracking(
    crawler: CrawlerEngine,
    category: Any,
    job_id: UUID,
    correlation_id: str
) -> tuple[int, int]:
    """Execute crawler with job progress tracking.
    
    Args:
        crawler: CrawlerEngine instance
        category: Category object to crawl
        job_id: Job UUID for tracking
        correlation_id: Correlation ID for logging
        
    Returns:
        Tuple of (articles_found, articles_saved)
    """
    try:
        # Execute crawl using the enhanced method
        extracted_articles = await crawler.crawl_category_advanced(category)
        
        articles_found = len(extracted_articles)
        
        # The crawler already saves articles, so we get the count from the result
        articles_saved = 0
        for article in extracted_articles:
            if article.get('saved', False):
                articles_saved += 1
        
        # If crawler doesn't provide saved info, use articles_found as approximation
        if articles_saved == 0 and articles_found > 0:
            articles_saved = articles_found
        
        logger.info("Crawl execution completed", extra={
            "correlation_id": correlation_id,
            "job_id": str(job_id),
            "articles_found": articles_found,
            "articles_saved": articles_saved,
            "category_name": category.name
        })
        
        return articles_found, articles_saved
        
    except Exception as e:
        logger.error(f"Crawl execution failed: {e}", extra={
            "correlation_id": correlation_id,
            "job_id": str(job_id),
            "category_name": category.name,
            "error_type": type(e).__name__
        })
        raise


async def _handle_task_error(
    task_instance,
    exception: Exception,
    job_id: UUID,
    job_repo: CrawlJobRepository,
    correlation_id: str,
    error_category: str
) -> Dict[str, Any]:
    """Comprehensive error handling for Celery tasks with retry logic and alerting.
    
    Args:
        task_instance: Celery task instance for retry handling
        exception: The exception that occurred
        job_id: Job UUID for status tracking
        job_repo: Repository for job status updates
        correlation_id: Correlation ID for logging
        error_category: Category of error for differentiated handling
        
    Returns:
        Error handling result dictionary
    """
    alert_manager = get_alert_manager()
    
    # Extract error details
    if isinstance(exception, BaseAppException):
        error_msg = exception.message
        error_details = exception.details
        is_retryable = exception.retryable
        retry_after = exception.retry_after
    else:
        error_msg = str(exception)
        error_details = {"error_type": type(exception).__name__}
        is_retryable = True
        retry_after = None
    
    # Log the error with full context
    logger.error(f"Task failed with {error_category} error: {error_msg}", extra={
        "correlation_id": correlation_id,
        "error_category": error_category,
        "error_type": type(exception).__name__,
        "error_details": error_details,
        "job_id": str(job_id),
        "task_id": task_instance.request.id,
        "retry_count": task_instance.request.retries,
        "is_retryable": is_retryable
    })
    
    # Update job status
    try:
        await job_repo.update_status(
            job_id=job_id,
            status="failed",
            error_message=error_msg,
            completed_at=datetime.now(timezone.utc),
            error_details=error_details
        )
    except Exception as db_error:
        logger.error(f"Failed to update job status: {db_error}", extra={
            "correlation_id": correlation_id,
            "job_id": str(job_id)
        })
    
    # Determine retry behavior based on error category and exception properties
    should_retry = is_retryable and task_instance.request.retries < task_instance.max_retries
    
    if should_retry:
        countdown = _calculate_retry_countdown(error_category, task_instance.request.retries, retry_after)
        
        logger.info(f"Retrying task in {countdown} seconds", extra={
            "correlation_id": correlation_id,
            "retry_count": task_instance.request.retries + 1,
            "countdown": countdown,
            "error_category": error_category
        })
        
        # Send alert for repeated failures
        if task_instance.request.retries >= 1:
            await alert_manager.send_alert(
                alert_type=AlertType.TASK_FAILURE,
                severity=AlertSeverity.MEDIUM,
                message=f"Task retry #{task_instance.request.retries + 1}: {error_msg}",
                details={
                    "task_name": "crawl_category_task",
                    "job_id": str(job_id),
                    "error_category": error_category,
                    "retry_count": task_instance.request.retries + 1,
                    "countdown": countdown
                },
                correlation_id=correlation_id
            )
        
        raise task_instance.retry(countdown=countdown)
    
    # No more retries - final failure
    logger.error(f"Task failed permanently after {task_instance.request.retries} retries", extra={
        "correlation_id": correlation_id,
        "error_category": error_category,
        "final_error": error_msg
    })
    
    # Send critical alert for final failure
    alert_severity = _get_alert_severity_for_error_category(error_category)
    alert_type = _get_alert_type_for_error_category(error_category)
    
    await alert_manager.send_alert(
        alert_type=alert_type,
        severity=alert_severity,
        message=f"Task failed permanently: {error_msg}",
        details={
            "task_name": "crawl_category_task",
            "job_id": str(job_id),
            "error_category": error_category,
            "total_attempts": task_instance.request.retries + 1,
            "error_details": error_details
        },
        correlation_id=correlation_id
    )
    
    return {
        "status": "failed",
        "error": error_msg,
        "error_category": error_category,
        "retry_exhausted": True,
        "total_attempts": task_instance.request.retries + 1,
        "correlation_id": correlation_id
    }


def _calculate_retry_countdown(error_category: str, retry_count: int, retry_after: Optional[int]) -> int:
    """Calculate retry countdown based on error category and retry count.
    
    Args:
        error_category: Category of error
        retry_count: Current retry count (0-based)
        retry_after: Specific retry delay from exception
        
    Returns:
        Countdown in seconds
    """
    if retry_after:
        return retry_after
    
    # Different retry strategies for different error categories
    retry_strategies = {
        "rate_limit": lambda count: 900 + (300 * count),  # 15+ minutes, increasing
        "external_service": lambda count: min(60 * (2 ** count), 300),  # Exponential, max 5 minutes
        "database": lambda count: min(30 * (2 ** count), 120),  # Exponential, max 2 minutes
        "application": lambda count: min(60 * (2 ** count), 180),  # Exponential, max 3 minutes
        "unexpected": lambda count: min(120 * (2 ** count), 600)  # Exponential, max 10 minutes
    }
    
    strategy = retry_strategies.get(error_category, retry_strategies["application"])
    return strategy(retry_count)


def _get_alert_severity_for_error_category(error_category: str) -> AlertSeverity:
    """Get appropriate alert severity for error category."""
    severity_map = {
        "rate_limit": AlertSeverity.MEDIUM,
        "external_service": AlertSeverity.HIGH,
        "database": AlertSeverity.CRITICAL,
        "application": AlertSeverity.HIGH,
        "unexpected": AlertSeverity.CRITICAL
    }
    return severity_map.get(error_category, AlertSeverity.HIGH)


def _get_alert_type_for_error_category(error_category: str) -> AlertType:
    """Get appropriate alert type for error category."""
    type_map = {
        "rate_limit": AlertType.RATE_LIMIT_EXCEEDED,
        "external_service": AlertType.EXTERNAL_SERVICE_UNAVAILABLE,
        "database": AlertType.DATABASE_CONNECTION_FAILED,
        "application": AlertType.TASK_FAILURE,
        "unexpected": AlertType.TASK_FAILURE
    }
    return type_map.get(error_category, AlertType.TASK_FAILURE)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def cleanup_old_jobs_task(self) -> Dict[str, Any]:
    """Clean up old completed and failed jobs.
    
    This maintenance task removes old job records to prevent database bloat.
    Runs periodically via Celery Beat scheduler.
    
    Returns:
        Cleanup results and statistics
    """
    correlation_id = f"cleanup_{self.request.id}"
    settings = get_settings()
    
    logger.info("Starting job cleanup task", extra={
        "correlation_id": correlation_id,
        "task_id": self.request.id
    })
    
    return asyncio.run(_async_cleanup_old_jobs_task(self, correlation_id, settings))


async def _async_cleanup_old_jobs_task(
    task_instance,
    correlation_id: str,
    settings
) -> Dict[str, Any]:
    """Async implementation of job cleanup task.
    
    Args:
        task_instance: Celery task instance
        correlation_id: Unique correlation ID
        settings: Application settings
        
    Returns:
        Cleanup results
    """
    try:
        job_repo = CrawlJobRepository()
        cleanup_days = settings.JOB_CLEANUP_DAYS
        
        # Clean up old jobs
        cleaned_count = await job_repo.cleanup_old_jobs(days_old=cleanup_days)
        
        # Reset stuck jobs if any
        stuck_count = await job_repo.reset_stuck_jobs(stuck_threshold_hours=2)
        
        result = {
            "status": "completed",
            "jobs_cleaned": cleaned_count,
            "stuck_jobs_reset": stuck_count,
            "cleanup_days": cleanup_days,
            "correlation_id": correlation_id
        }
        
        logger.info("Job cleanup completed", extra={
            "correlation_id": correlation_id,
            **result
        })
        
        return result
        
    except Exception as e:
        error_msg = f"Job cleanup failed: {str(e)}"
        logger.error(error_msg, extra={
            "correlation_id": correlation_id,
            "error_type": type(e).__name__
        })
        
        # Retry cleanup with delay
        if task_instance.request.retries < task_instance.max_retries:
            countdown = 120 * (task_instance.request.retries + 1)
            logger.info(f"Retrying cleanup task in {countdown} seconds", extra={
                "correlation_id": correlation_id,
                "retry_count": task_instance.request.retries + 1
            })
            raise task_instance.retry(countdown=countdown)
        
        return {
            "status": "failed",
            "error": error_msg,
            "correlation_id": correlation_id
        }


@celery_app.task(bind=True, max_retries=1)
def monitor_job_health_task(self) -> Dict[str, Any]:
    """Monitor job queue health and detect issues.
    
    This maintenance task checks for stuck jobs, queue backlogs,
    and other health issues in the job system.
    
    Returns:
        Health monitoring results
    """
    correlation_id = f"health_{self.request.id}"
    
    logger.info("Starting job health monitoring", extra={
        "correlation_id": correlation_id,
        "task_id": self.request.id
    })
    
    return asyncio.run(_async_monitor_job_health_task(self, correlation_id))


async def _async_monitor_job_health_task(
    task_instance,
    correlation_id: str
) -> Dict[str, Any]:
    """Async implementation of health monitoring task.
    
    Args:
        task_instance: Celery task instance
        correlation_id: Unique correlation ID
        
    Returns:
        Health monitoring results
    """
    try:
        job_repo = CrawlJobRepository()
        
        # Get active jobs counts
        active_jobs = await job_repo.get_active_jobs(limit=1000)
        running_jobs = await job_repo.get_running_jobs(limit=100)
        
        # Check for stuck jobs
        stuck_jobs = await job_repo.get_stuck_jobs(stuck_threshold_hours=2)
        
        # Get recent statistics
        from_date = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await job_repo.get_job_statistics(from_date=from_date)
        
        # Evaluate health status
        health_issues = []
        health_status = "healthy"
        
        if len(stuck_jobs) > 0:
            health_issues.append(f"{len(stuck_jobs)} jobs appear stuck")
            health_status = "degraded"
        
        if len(active_jobs) > 100:
            health_issues.append(f"High queue backlog: {len(active_jobs)} active jobs")
            if health_status == "healthy":
                health_status = "degraded"
        
        if len(running_jobs) == 0 and len(active_jobs) > 10:
            health_issues.append("No running jobs but pending jobs exist")
            health_status = "unhealthy"
        
        # Calculate success rate for last 24h
        total_completed = stats["status_counts"].get("completed", 0)
        total_failed = stats["status_counts"].get("failed", 0)
        total_finished = total_completed + total_failed
        
        success_rate = total_completed / total_finished if total_finished > 0 else 1.0
        
        if success_rate < 0.8:
            health_issues.append(f"Low success rate: {success_rate:.1%}")
            health_status = "degraded"
        
        result = {
            "status": "completed",
            "health_status": health_status,
            "health_issues": health_issues,
            "active_jobs": len(active_jobs),
            "running_jobs": len(running_jobs),
            "stuck_jobs": len(stuck_jobs),
            "success_rate_24h": success_rate,
            "jobs_completed_24h": total_completed,
            "jobs_failed_24h": total_failed,
            "correlation_id": correlation_id
        }
        
        if health_status != "healthy":
            logger.warning("Job health issues detected", extra={
                "correlation_id": correlation_id,
                **result
            })
        else:
            logger.info("Job system healthy", extra={
                "correlation_id": correlation_id,
                **result
            })
        
        return result
        
    except Exception as e:
        error_msg = f"Health monitoring failed: {str(e)}"
        logger.error(error_msg, extra={
            "correlation_id": correlation_id,
            "error_type": type(e).__name__
        })
        
        return {
            "status": "failed",
            "error": error_msg,
            "correlation_id": correlation_id
        }


@celery_app.task(bind=True, max_retries=3)
def trigger_category_crawl_task(
    self,
    category_id: str,
    priority: int = 0,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Trigger a new crawl job for a specific category.
    
    This task creates a new job record and schedules the actual crawl task.
    It's useful for manual triggering or API-driven crawling.
    
    Args:
        category_id: UUID string of category to crawl
        priority: Job priority (higher = more important)
        metadata: Optional metadata for the job
        
    Returns:
        Job creation and scheduling results
    """
    correlation_id = f"trigger_{self.request.id}"
    
    logger.info("Triggering category crawl", extra={
        "correlation_id": correlation_id,
        "category_id": category_id,
        "priority": priority,
        "task_id": self.request.id
    })
    
    return asyncio.run(_async_trigger_category_crawl_task(
        self, category_id, priority, metadata, correlation_id
    ))


async def _async_trigger_category_crawl_task(
    task_instance,
    category_id: str,
    priority: int,
    metadata: Optional[Dict[str, Any]],
    correlation_id: str
) -> Dict[str, Any]:
    """Async implementation of category crawl triggering.
    
    Args:
        task_instance: Celery task instance
        category_id: Category UUID string
        priority: Job priority
        metadata: Optional job metadata
        correlation_id: Correlation ID
        
    Returns:
        Triggering results
    """
    try:
        # Validate category exists and is active
        category_repo = CategoryRepository()
        category = await category_repo.get_by_id(UUID(category_id))
        
        if not category:
            error_msg = f"Category {category_id} not found"
            return {"status": "failed", "error": error_msg}
        
        if not category.is_active:
            error_msg = f"Category {category.name} is not active"
            return {"status": "failed", "error": error_msg}
        
        # Create new job record
        job_repo = CrawlJobRepository()
        job = await job_repo.create_job(
            category_id=UUID(category_id),
            priority=priority,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        
        # Schedule the actual crawl task
        crawl_result = crawl_category_task.delay(
            category_id=category_id,
            job_id=str(job.id)
        )
        
        result = {
            "status": "scheduled",
            "job_id": str(job.id),
            "category_name": category.name,
            "celery_task_id": crawl_result.id,
            "priority": priority,
            "correlation_id": correlation_id
        }
        
        logger.info("Category crawl scheduled", extra={
            "correlation_id": correlation_id,
            **result
        })
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to trigger category crawl: {str(e)}"
        logger.error(error_msg, extra={
            "correlation_id": correlation_id,
            "category_id": category_id,
            "error_type": type(e).__name__
        })
        
        return {
            "status": "failed",
            "error": error_msg,
            "correlation_id": correlation_id
        }


# Task registration with Celery
__all__ = [
    "crawl_category_task",
    "cleanup_old_jobs_task", 
    "monitor_job_health_task",
    "trigger_category_crawl_task"
]