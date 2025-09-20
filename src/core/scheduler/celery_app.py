import logging
from celery import Celery
from kombu import Queue
from kombu.serialization import register

from src.shared.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "google_news_scraper",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "src.core.scheduler.tasks"
    ]
)

celery_app.conf.update(
    # Serialization settings
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    
    # Time and timezone settings
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    
    # Task tracking settings
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,
    
    # Worker settings
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    
    # Task routing settings
    task_routes={
        "src.core.scheduler.tasks.crawl_category_task": {"queue": "crawl_queue"},
        "src.core.scheduler.tasks.trigger_category_crawl_task": {"queue": "default"},
        "src.core.scheduler.tasks.cleanup_old_jobs_task": {"queue": "maintenance_queue"},
        "src.core.scheduler.tasks.monitor_job_health_task": {"queue": "maintenance_queue"},
    },
    
    # Default queue settings
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("crawl_queue", routing_key="crawl_queue"),
        Queue("maintenance_queue", routing_key="maintenance_queue"),
    ),
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    task_result_expires=3600,
    result_persistent=True,
    
    # Retry and timeout settings
    task_soft_time_limit=settings.JOB_EXECUTION_TIMEOUT - 60,  # 1 minute before hard limit
    task_time_limit=settings.JOB_EXECUTION_TIMEOUT,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # Redis connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    # Monitoring settings
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Error handling
    task_annotations={
        '*': {
            'rate_limit': '100/m',  # Max 100 tasks per minute per worker
        },
        'src.core.scheduler.tasks.crawl_category_task': {
            'rate_limit': '20/m',   # Max 20 crawl tasks per minute
            'time_limit': settings.JOB_EXECUTION_TIMEOUT,
            'soft_time_limit': settings.JOB_EXECUTION_TIMEOUT - 60,
        },
        'src.core.scheduler.tasks.cleanup_old_jobs_task': {
            'rate_limit': '1/h',    # Max 1 cleanup task per hour
        },
    },
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-old-jobs": {
        "task": "src.core.scheduler.tasks.cleanup_old_jobs_task",
        "schedule": 3600.0,  # Run every hour
        "options": {"queue": "maintenance_queue"},
    },
    "monitor-job-health": {
        "task": "src.core.scheduler.tasks.monitor_job_health_task",
        "schedule": 300.0,  # Run every 5 minutes
        "options": {"queue": "maintenance_queue"},
    },
}

# Health check function for Celery
def check_celery_health():
    """
    Check if Celery is healthy and can process tasks
    
    Returns:
        dict: Health status information
    """
    try:
        # Check if broker is accessible
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {
                "status": "unhealthy",
                "message": "No active workers found",
                "broker": settings.CELERY_BROKER_URL
            }
        
        # Get worker information
        active_workers = len(stats)
        active_tasks = inspect.active()
        reserved_tasks = inspect.reserved()
        
        total_active = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values()) if reserved_tasks else 0
        
        return {
            "status": "healthy",
            "active_workers": active_workers,
            "active_tasks": total_active,
            "reserved_tasks": total_reserved,
            "broker": settings.CELERY_BROKER_URL,
            "backend": settings.CELERY_RESULT_BACKEND
        }
        
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": str(e),
            "broker": settings.CELERY_BROKER_URL
        }

# Configure logging for Celery
def setup_celery_logging():
    """Setup structured logging for Celery tasks"""
    import structlog
    
    # Configure structlog for Celery
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Auto setup logging when module is imported
setup_celery_logging()

logger.info("Celery app initialized", extra={
    "broker": settings.CELERY_BROKER_URL,
    "backend": settings.CELERY_RESULT_BACKEND,
    "timeout": settings.JOB_EXECUTION_TIMEOUT
})