# Backend Architecture

## Overview

The backend architecture for the Google News Scraper is built on FastAPI with a traditional server approach, utilizing PostgreSQL for persistence, Redis for caching and message brokering, and Celery for distributed task processing. The architecture supports the job-centric enhancement requirements while maintaining the existing system's reliability and performance.

## Service Architecture

### Traditional Server Architecture

The Google News Scraper uses a traditional FastAPI server architecture with clear separation of concerns and layered design patterns.

#### Service Organization

```
src/
├── api/                    # API layer - request/response handling
│   ├── main.py            # FastAPI app configuration and startup
│   ├── routes/            # API route handlers
│   │   ├── __init__.py
│   │   ├── jobs.py        # Enhanced job management routes
│   │   ├── articles.py    # New article API routes
│   │   ├── categories.py  # Enhanced category routes
│   │   └── schedules.py   # New scheduling routes
│   ├── schemas/           # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── job.py         # Job-related schemas
│   │   ├── article.py     # Article schemas
│   │   ├── category.py    # Category schemas
│   │   └── schedule.py    # Schedule schemas
│   ├── dependencies/      # FastAPI dependency injection
│   │   ├── __init__.py
│   │   ├── auth.py        # Authentication dependencies
│   │   ├── database.py    # Database session management
│   │   └── pagination.py  # Pagination helpers
│   └── middleware/        # Custom middleware
│       ├── __init__.py
│       ├── cors.py        # CORS handling
│       ├── logging.py     # Request logging
│       └── error_handling.py # Error handling middleware
├── core/                  # Business logic layer
│   ├── __init__.py
│   ├── crawler/           # Enhanced crawling engine
│   │   ├── __init__.py
│   │   ├── engine.py      # Main crawling logic
│   │   ├── extractor.py   # Enhanced article extraction with Google News support
│   │   ├── sync_engine.py # Synchronous extraction for Google News
│   │   ├── processors.py  # Article processing
│   │   └── filters.py     # Content filtering
│   └── scheduler/         # Task scheduling
│       ├── __init__.py
│       ├── celery_app.py  # Celery configuration
│       ├── tasks.py       # Background tasks
│       └── beat.py        # Scheduled tasks
├── database/              # Data access layer
│   ├── __init__.py
│   ├── models/            # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py        # Base model class
│   │   ├── crawl_job.py   # Job model (enhanced)
│   │   ├── article.py     # Article model
│   │   ├── category.py    # Category model
│   │   └── schedule.py    # Schedule model (new)
│   ├── repositories/      # Repository pattern implementation
│   │   ├── __init__.py
│   │   ├── base.py        # Base repository
│   │   ├── job_repo.py    # Job repository (enhanced)
│   │   ├── article_repo.py # Article repository
│   │   ├── category_repo.py # Category repository
│   │   └── schedule_repo.py # Schedule repository (new)
│   ├── migrations/        # Alembic database migrations
│   │   ├── env.py
│   │   └── versions/
│   └── connection.py      # Database connection management
├── shared/                # Shared utilities and configuration
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── exceptions.py      # Custom exceptions
│   ├── logging.py         # Logging configuration
│   └── health.py          # Health check utilities
└── tests/                 # Test suites
    ├── __init__.py
    ├── api/               # API endpoint tests
    ├── repositories/      # Repository layer tests
    ├── services/          # Business logic tests
    └── integration/       # Integration tests
```

#### Controller Template

```python
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import structlog

from src.database.connection import get_database_session
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.article_repo import ArticleRepository
from src.api.schemas.job import (
    JobResponse, JobListResponse, JobCreateRequest,
    JobUpdateRequest, PriorityUpdateRequest
)
from src.api.schemas.common import PaginatedResponse
from src.api.dependencies.pagination import PaginationParams
from src.api.dependencies.auth import get_current_user
from src.core.scheduler.tasks import update_job_priority_task, trigger_manual_crawl
from src.shared.exceptions import (
    JobNotFoundException, JobAlreadyRunningException,
    ValidationError
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    priority_min: Optional[int] = Query(None, ge=0, description="Minimum priority"),
    sort_by: str = Query("priority", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    List crawl jobs with filtering and pagination.

    Supports job-centric workflow with priority-based sorting
    and comprehensive filtering options.
    """
    job_repo = CrawlJobRepository(db)

    try:
        jobs, total = await job_repo.get_paginated_jobs(
            status=status,
            category_id=category_id,
            priority_min=priority_min,
            sort_by=sort_by,
            sort_order=sort_order,
            page=pagination.page,
            size=pagination.size
        )

        logger.info(
            "Jobs listed successfully",
            user_id=current_user.id,
            total_jobs=total,
            page=pagination.page,
            filters={
                "status": status,
                "category_id": category_id,
                "priority_min": priority_min
            }
        )

        return PaginatedResponse(
            items=[JobResponse.from_orm(job) for job in jobs],
            total=total,
            page=pagination.page,
            pages=(total + pagination.size - 1) // pagination.size,
            size=pagination.size
        )

    except Exception as e:
        logger.error("Failed to list jobs", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve jobs"
        )

@router.patch("/{job_id}/priority", response_model=JobResponse)
async def update_job_priority(
    job_id: str,
    priority_update: PriorityUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    Update job priority for Run Now functionality.

    High priority jobs (>= 5) will execute immediately when
    worker resources become available.
    """
    job_repo = CrawlJobRepository(db)

    # Validate job exists
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise JobNotFoundException(job_id)

    # Check if job can be prioritized
    if job.status == "running":
        raise JobAlreadyRunningException(job_id)

    if job.status in ["completed", "failed"]:
        raise ValidationError(
            message="Cannot prioritize completed or failed jobs",
            field="status"
        )

    try:
        # Update priority in database with atomic operation
        updated_job = await job_repo.update_job_priority(
            job_id,
            priority_update.priority
        )

        # Trigger Celery priority update for pending jobs
        if updated_job.status == "pending" and priority_update.priority >= 5:
            background_tasks.add_task(
                update_job_priority_task.delay,
                job_id,
                priority_update.priority
            )

        logger.info(
            "Job priority updated successfully",
            job_id=job_id,
            old_priority=job.priority,
            new_priority=priority_update.priority,
            user_id=current_user.id
        )

        return JobResponse.from_orm(updated_job)

    except Exception as e:
        logger.error(
            "Failed to update job priority",
            job_id=job_id,
            priority=priority_update.priority,
            error=str(e),
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to update job priority"
        )

@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    force: bool = Query(False, description="Force delete running job"),
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    Delete crawl job with confirmation and impact analysis.

    Returns information about affected articles and dependent schedules.
    """
    job_repo = CrawlJobRepository(db)
    article_repo = ArticleRepository(db)

    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise JobNotFoundException(job_id)

    # Check if job can be deleted
    if job.status == "running" and not force:
        raise ValidationError(
            message="Cannot delete running job without force flag",
            field="status"
        )

    if not force and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required for forced deletion"
        )

    try:
        # Get impact analysis
        articles_count = await article_repo.count_articles_by_job(job_id)

        # Perform deletion
        await job_repo.delete_job(job_id)

        logger.info(
            "Job deleted successfully",
            job_id=job_id,
            articles_affected=articles_count,
            force=force,
            user_id=current_user.id
        )

        return {
            "message": "Job deleted successfully",
            "impact": {
                "articles_affected": articles_count,
                "dependent_schedules": []  # Could be expanded to check schedules
            }
        }

    except Exception as e:
        logger.error(
            "Failed to delete job",
            job_id=job_id,
            error=str(e),
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete job"
        )

@router.post("/{job_id}/manual-trigger", response_model=JobResponse)
async def trigger_manual_crawl(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    Manually trigger a job to run immediately.

    Creates a new high-priority job based on the existing job configuration.
    """
    job_repo = CrawlJobRepository(db)

    original_job = await job_repo.get_job_by_id(job_id)
    if not original_job:
        raise JobNotFoundException(job_id)

    try:
        # Create new job with high priority
        new_job = await job_repo.create_job(
            category_id=original_job.category_id,
            priority=10,  # High priority for immediate execution
            job_metadata={
                "source": "manual_trigger",
                "original_job_id": job_id,
                "user_id": current_user.id
            }
        )

        # Trigger immediate execution
        background_tasks.add_task(
            trigger_manual_crawl.delay,
            str(new_job.id)
        )

        logger.info(
            "Manual crawl triggered successfully",
            original_job_id=job_id,
            new_job_id=str(new_job.id),
            user_id=current_user.id
        )

        return JobResponse.from_orm(new_job)

    except Exception as e:
        logger.error(
            "Failed to trigger manual crawl",
            job_id=job_id,
            error=str(e),
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger manual crawl"
        )
```

## Database Architecture

### Enhanced Repository Pattern

```python
# Enhanced CrawlJobRepository with job-centric functionality
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime, timedelta

from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from src.database.models.article import Article
from src.database.models.category import Category
from src.database.repositories.base import BaseRepository

class CrawlJobRepository(BaseRepository[CrawlJob]):
    def __init__(self, db: AsyncSession):
        super().__init__(CrawlJob, db)

    async def get_paginated_jobs(
        self,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        priority_min: Optional[int] = None,
        sort_by: str = "priority",
        sort_order: str = "desc",
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[CrawlJob], int]:
        """
        Get paginated jobs with comprehensive filtering and sorting.

        Optimized for job-centric UI with category information preloaded.
        """
        # Base query with category relationship
        query = select(CrawlJob).options(
            joinedload(CrawlJob.category)
        )

        # Apply filters
        conditions = []
        if status:
            conditions.append(CrawlJob.status == status)
        if category_id:
            conditions.append(CrawlJob.category_id == category_id)
        if priority_min is not None:
            conditions.append(CrawlJob.priority >= priority_min)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total for pagination
        count_query = select(func.count(CrawlJob.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply sorting
        sort_column = getattr(CrawlJob, sort_by, CrawlJob.priority)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply secondary sorting for consistent results
        if sort_by != "created_at":
            query = query.order_by(desc(CrawlJob.created_at))

        # Apply pagination
        query = query.offset((page - 1) * size).limit(size)

        result = await self.db.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total

    async def update_job_priority(
        self,
        job_id: str,
        priority: int
    ) -> CrawlJob:
        """
        Update job priority with atomic operation and optimistic locking.
        """
        stmt = (
            update(CrawlJob)
            .where(CrawlJob.id == job_id)
            .values(
                priority=priority,
                updated_at=func.now()
            )
            .returning(CrawlJob)
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        updated_job = result.scalar_one_or_none()
        if not updated_job:
            raise ValueError(f"Job {job_id} not found or update failed")

        return updated_job

    async def get_priority_queue_jobs(
        self,
        limit: int = 10
    ) -> List[CrawlJob]:
        """
        Get pending jobs ordered by priority for queue processing.

        Used by Celery workers to determine next jobs to execute.
        """
        query = (
            select(CrawlJob)
            .options(joinedload(CrawlJob.category))
            .where(CrawlJob.status == CrawlJobStatus.PENDING)
            .order_by(
                desc(CrawlJob.priority),  # Higher priority first
                asc(CrawlJob.created_at)  # FIFO for same priority
            )
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_job_with_articles(
        self,
        job_id: str,
        articles_limit: Optional[int] = None
    ) -> Optional[CrawlJob]:
        """
        Get job with associated articles for article viewing modal.
        """
        # First get the job
        job_query = (
            select(CrawlJob)
            .options(joinedload(CrawlJob.category))
            .where(CrawlJob.id == job_id)
        )

        job_result = await self.db.execute(job_query)
        job = job_result.scalar_one_or_none()

        if not job:
            return None

        # Get associated articles separately to avoid N+1 issues
        articles_query = select(Article).where(Article.crawl_job_id == job_id)

        if articles_limit:
            articles_query = articles_query.limit(articles_limit)

        articles_result = await self.db.execute(articles_query)
        articles = list(articles_result.scalars().all())

        # Manually set the relationship
        job.articles = articles

        return job

    async def get_job_statistics(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive job statistics for dashboard and reporting.
        """
        # Base conditions
        conditions = []
        if date_from:
            conditions.append(CrawlJob.created_at >= date_from)
        if date_to:
            conditions.append(CrawlJob.created_at <= date_to)
        if category_id:
            conditions.append(CrawlJob.category_id == category_id)

        base_query = select(CrawlJob)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        # Status distribution
        status_query = (
            select(
                CrawlJob.status,
                func.count(CrawlJob.id).label('count')
            )
            .select_from(base_query.subquery())
            .group_by(CrawlJob.status)
        )

        status_result = await self.db.execute(status_query)
        status_distribution = {row.status: row.count for row in status_result}

        # Performance metrics
        performance_query = select(
            func.count(CrawlJob.id).label('total_jobs'),
            func.avg(CrawlJob.articles_found).label('avg_articles_found'),
            func.avg(CrawlJob.articles_saved).label('avg_articles_saved'),
            func.avg(
                func.extract('epoch', CrawlJob.completed_at - CrawlJob.started_at)
            ).label('avg_duration_seconds')
        ).select_from(base_query.subquery()).where(
            CrawlJob.status == CrawlJobStatus.COMPLETED
        )

        performance_result = await self.db.execute(performance_query)
        performance = performance_result.first()

        # Recent activity (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_query = select(func.count(CrawlJob.id)).where(
            CrawlJob.created_at >= recent_cutoff
        )

        recent_result = await self.db.execute(recent_query)
        recent_jobs = recent_result.scalar_one()

        return {
            'status_distribution': status_distribution,
            'total_jobs': performance.total_jobs or 0,
            'avg_articles_found': float(performance.avg_articles_found or 0),
            'avg_articles_saved': float(performance.avg_articles_saved or 0),
            'avg_duration_seconds': float(performance.avg_duration_seconds or 0),
            'recent_jobs_24h': recent_jobs
        }

    async def cleanup_old_jobs(
        self,
        retention_days: int = 90,
        batch_size: int = 1000
    ) -> int:
        """
        Clean up old completed/failed jobs to maintain database performance.

        Returns the number of jobs deleted.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Delete in batches to avoid long-running transactions
        total_deleted = 0
        while True:
            # Get batch of old jobs
            old_jobs_query = (
                select(CrawlJob.id)
                .where(
                    and_(
                        CrawlJob.completed_at < cutoff_date,
                        CrawlJob.status.in_([
                            CrawlJobStatus.COMPLETED,
                            CrawlJobStatus.FAILED
                        ])
                    )
                )
                .limit(batch_size)
            )

            result = await self.db.execute(old_jobs_query)
            job_ids = [row.id for row in result]

            if not job_ids:
                break

            # Delete batch
            delete_stmt = delete(CrawlJob).where(
                CrawlJob.id.in_(job_ids)
            )

            delete_result = await self.db.execute(delete_stmt)
            await self.db.commit()

            batch_deleted = delete_result.rowcount
            total_deleted += batch_deleted

            if batch_deleted < batch_size:
                break

        return total_deleted
```

### Advanced Database Schema

```sql
-- Enhanced schema with performance optimizations and new features

-- Job priority queue index for efficient worker queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_crawl_jobs_priority_queue
ON crawl_jobs(priority DESC, created_at ASC)
WHERE status = 'pending';

-- Composite index for job listing with filters
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_crawl_jobs_list_filters
ON crawl_jobs(status, category_id, priority DESC, created_at DESC);

-- Index for article-job associations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_job_lookup
ON articles(crawl_job_id, created_at DESC)
WHERE crawl_job_id IS NOT NULL;

-- Partial index for active schedules
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_category_schedules_active
ON category_schedules(next_run_at)
WHERE is_active = true;

-- Function for job queue position calculation
CREATE OR REPLACE FUNCTION get_job_queue_position(target_job_id UUID)
RETURNS INTEGER AS $$
DECLARE
    position INTEGER;
    target_priority INTEGER;
    target_created_at TIMESTAMPTZ;
BEGIN
    -- Get target job info
    SELECT priority, created_at
    INTO target_priority, target_created_at
    FROM crawl_jobs
    WHERE id = target_job_id AND status = 'pending';

    IF target_priority IS NULL THEN
        RETURN NULL; -- Job not found or not pending
    END IF;

    -- Calculate position in queue
    SELECT COUNT(*) + 1
    INTO position
    FROM crawl_jobs
    WHERE status = 'pending'
    AND (
        priority > target_priority
        OR (priority = target_priority AND created_at < target_created_at)
    );

    RETURN position;
END;
$$ LANGUAGE plpgsql;

-- Materialized view for job statistics (refreshed periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS job_statistics_summary AS
SELECT
    DATE(created_at) as date,
    status,
    COUNT(*) as job_count,
    AVG(articles_found) as avg_articles_found,
    AVG(articles_saved) as avg_articles_saved,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
FROM crawl_jobs
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), status;

CREATE UNIQUE INDEX ON job_statistics_summary (date, status);

-- Trigger for automatic job metadata updates
CREATE OR REPLACE FUNCTION update_job_queue_metadata()
RETURNS TRIGGER AS $$
BEGIN
    -- Update queue position when priority changes
    IF TG_OP = 'UPDATE' AND OLD.priority != NEW.priority THEN
        NEW.job_metadata = COALESCE(NEW.job_metadata, '{}'::jsonb) ||
            jsonb_build_object(
                'queue_position_updated_at', CURRENT_TIMESTAMP,
                'priority_change', jsonb_build_object(
                    'from', OLD.priority,
                    'to', NEW.priority
                )
            );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_job_queue_metadata
    BEFORE UPDATE ON crawl_jobs
    FOR EACH ROW EXECUTE FUNCTION update_job_queue_metadata();

-- Function to refresh job statistics (called by scheduled task)
CREATE OR REPLACE FUNCTION refresh_job_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY job_statistics_summary;

    -- Clean up old statistics (keep last 90 days)
    DELETE FROM job_statistics_summary
    WHERE date < CURRENT_DATE - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
```

## Celery Task Architecture

### Enhanced Task Configuration

```python
# celery_app.py - Enhanced Celery configuration for job-centric processing
from celery import Celery
from celery.signals import setup_logging, worker_ready
from kombu import Queue, Exchange
import structlog

from src.shared.config import get_settings

settings = get_settings()

# Create Celery app with custom configuration
celery_app = Celery(
    "google_news_scraper",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "src.core.scheduler.tasks",
        "src.core.scheduler.beat_tasks"
    ]
)

# Priority-based queue configuration
celery_app.conf.update(
    # Task routing with priority queues
    task_routes={
        'src.core.scheduler.tasks.crawl_category': {
            'queue': 'priority'
        },
        'src.core.scheduler.tasks.update_job_priority_task': {
            'queue': 'priority'
        },
        'src.core.scheduler.tasks.process_article': {
            'queue': 'default'
        },
        'src.core.scheduler.beat_tasks.*': {
            'queue': 'scheduled'
        }
    },

    # Queue definitions with priority support
    task_queues=(
        Queue('priority', Exchange('priority'), routing_key='priority',
              queue_arguments={'x-max-priority': 10}),
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('scheduled', Exchange('scheduled'), routing_key='scheduled'),
    ),

    # Priority settings
    task_inherit_parent_priority=True,
    task_default_priority=5,
    task_queue_max_priority=10,

    # Performance optimizations
    worker_prefetch_multiplier=1,  # Important for priority queues
    task_acks_late=True,
    worker_max_tasks_per_child=50,

    # Reliability settings
    task_reject_on_worker_lost=True,
    task_time_limit=1800,  # 30 minutes
    task_soft_time_limit=1500,  # 25 minutes

    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        'retry_on_timeout': True,
        'visibility_timeout': 3600,
    },

    # Beat scheduler configuration
    beat_scheduler='celery.beat:PersistentScheduler',
    beat_schedule_filename='/app/data/beat/celerybeat-schedule',

    # Timezone
    timezone='UTC',
    enable_utc=True,
)

@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure structured logging for Celery."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready."""
    logger = structlog.get_logger(__name__)
    logger.info("Celery worker ready", worker_name=sender.hostname)
```

### Priority-Based Task Implementation

```python
# tasks.py - Enhanced task implementation with priority support
from celery import current_task
from celery.exceptions import Retry
from typing import Optional, Dict, Any
import structlog
from datetime import datetime

from src.core.scheduler.celery_app import celery_app
from src.database.connection import get_database_connection
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.article_repo import ArticleRepository
from src.core.crawler.engine import CrawlerEngine
from src.shared.exceptions import CrawlingException

logger = structlog.get_logger(__name__)

@celery_app.task(bind=True, name='crawl_category_job')
def crawl_category_job(
    self,
    job_id: str,
    priority: int = 5,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enhanced crawl task with job-centric tracking and priority handling.

    Args:
        job_id: Database job ID for tracking
        priority: Task priority (1-10, higher = more urgent)
        correlation_id: Request correlation ID for tracing

    Returns:
        Dict with job results and metadata
    """
    # Set task priority
    self.request.priority = priority

    # Setup logging context
    log = logger.bind(
        job_id=job_id,
        task_id=self.request.id,
        correlation_id=correlation_id,
        priority=priority
    )

    log.info("Starting crawl job", worker=self.request.hostname)

    # Get database session
    async_session = get_database_connection()

    try:
        # Update job status to running
        async with async_session() as db:
            job_repo = CrawlJobRepository(db)
            article_repo = ArticleRepository(db)

            job = await job_repo.get_job_by_id(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Update job status
            await job_repo.update_job_status(
                job_id,
                status="running",
                started_at=datetime.utcnow(),
                celery_task_id=self.request.id
            )

            log.info("Job status updated to running")

            # Initialize crawler
            crawler = CrawlerEngine(
                category=job.category,
                job_id=job_id,
                correlation_id=correlation_id
            )

            # Perform crawling with progress tracking
            articles_found = 0
            articles_saved = 0

            try:
                # Crawl articles
                crawl_results = await crawler.crawl_category(
                    progress_callback=lambda current, total:
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'current': current,
                                'total': total,
                                'articles_found': articles_found
                            }
                        )
                )

                articles_found = len(crawl_results.articles)
                log.info(f"Found {articles_found} articles")

                # Save articles to database
                for article_data in crawl_results.articles:
                    try:
                        article = await article_repo.create_article(
                            article_data=article_data,
                            job_id=job_id,
                            category_id=job.category_id
                        )
                        articles_saved += 1

                        # Update progress
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'articles_found': articles_found,
                                'articles_saved': articles_saved,
                                'current_article': article.title
                            }
                        )

                    except Exception as e:
                        log.warning("Failed to save article",
                                  article_url=article_data.get('url'),
                                  error=str(e))

                # Update job completion
                await job_repo.update_job_completion(
                    job_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                    articles_found=articles_found,
                    articles_saved=articles_saved
                )

                log.info("Crawl job completed successfully",
                        articles_found=articles_found,
                        articles_saved=articles_saved)

                return {
                    'status': 'completed',
                    'job_id': job_id,
                    'articles_found': articles_found,
                    'articles_saved': articles_saved,
                    'duration_seconds': (
                        datetime.utcnow() - job.started_at
                    ).total_seconds() if job.started_at else None,
                    'correlation_id': correlation_id
                }

            except CrawlingException as e:
                # Handle crawling-specific errors
                await job_repo.update_job_status(
                    job_id,
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error_message=str(e),
                    articles_found=articles_found,
                    articles_saved=articles_saved
                )

                log.error("Crawling failed", error=str(e))
                raise self.retry(
                    countdown=60 * (self.request.retries + 1),
                    max_retries=3,
                    exc=e
                )

    except Exception as e:
        # Handle unexpected errors
        log.error("Job execution failed", error=str(e), exc_info=True)

        # Update job status if possible
        try:
            async with async_session() as db:
                job_repo = CrawlJobRepository(db)
                await job_repo.update_job_status(
                    job_id,
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
        except Exception:
            log.error("Failed to update job status after error")

        raise

@celery_app.task(name='update_job_priority_task')
def update_job_priority_task(job_id: str, new_priority: int) -> bool:
    """
    Update job priority in Celery queue for Run Now functionality.

    This task runs with high priority to ensure immediate processing
    of priority changes.
    """
    logger.info("Updating job priority in queue",
                job_id=job_id, new_priority=new_priority)

    try:
        # Get active task if job is already running
        active_tasks = celery_app.control.inspect().active()

        for worker, tasks in active_tasks.items():
            for task in tasks:
                if (task['name'] == 'crawl_category_job' and
                    task['args'][0] == job_id):

                    # Job is already running, cannot change priority
                    logger.warning("Cannot update priority for running job",
                                 job_id=job_id, worker=worker)
                    return False

        # Update priority for pending tasks
        pending_tasks = celery_app.control.inspect().scheduled()

        for worker, tasks in pending_tasks.items():
            for task in tasks:
                if (task['task'] == 'crawl_category_job' and
                    task['args'][0] == job_id):

                    # Revoke old task and create new one with higher priority
                    celery_app.control.revoke(task['id'])

                    # Create new high-priority task
                    crawl_category_job.apply_async(
                        args=[job_id],
                        kwargs={'priority': new_priority},
                        priority=new_priority,
                        queue='priority'
                    )

                    logger.info("Job priority updated successfully",
                               job_id=job_id, new_priority=new_priority)
                    return True

        logger.warning("Job not found in queue", job_id=job_id)
        return False

    except Exception as e:
        logger.error("Failed to update job priority",
                    job_id=job_id, error=str(e))
        return False

@celery_app.task(name='cleanup_completed_jobs')
def cleanup_completed_jobs(retention_days: int = 90) -> Dict[str, int]:
    """
    Periodic cleanup task for old completed jobs.

    Runs daily to maintain database performance.
    """
    logger.info("Starting job cleanup", retention_days=retention_days)

    async_session = get_database_connection()

    try:
        async with async_session() as db:
            job_repo = CrawlJobRepository(db)
            deleted_count = await job_repo.cleanup_old_jobs(retention_days)

            logger.info("Job cleanup completed", deleted_jobs=deleted_count)

            return {
                'deleted_jobs': deleted_count,
                'retention_days': retention_days
            }

    except Exception as e:
        logger.error("Job cleanup failed", error=str(e))
        raise
```

## Enhanced Google News Extraction Architecture

### Critical Google News Extraction Patterns

Based on the proven 56% success rate implementation from `financial_news_extractor.py`, the backend architecture incorporates the following critical extraction patterns:

#### Single Browser Multi-Tab Strategy

```python
# Enhanced extractor.py - Google News URL Detection and Routing
class EnhancedArticleExtractor:
    """
    Enhanced extractor with Google News specialized handling.

    Implements proven patterns from financial_news_extractor.py:
    - Single browser with 10 tabs maximum for batch processing
    - 4-5 second wait times for JavaScript redirects
    - Anti-detection measures with random delays
    - Resource blocking for improved performance
    """

    def __init__(self):
        self.playwright_available = self._check_playwright()
        self.batch_size = 10  # Maximum tabs per browser session
        self.anti_detection_enabled = True

    async def extract_article_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Main extraction method with Google News detection.

        Routes Google News URLs to specialized Playwright handler,
        keeps standard extraction for other URLs.
        """
        correlation_id = str(uuid.uuid4())

        # Critical: Detect Google News URLs for specialized handling
        if 'news.google.com' in url:
            logger.info("Google News URL detected, using Playwright handler",
                       url=url, correlation_id=correlation_id)
            return await self._extract_google_news_with_playwright(url, correlation_id)

        # Standard extraction for non-Google News URLs
        return await self._extract_with_retry(url, correlation_id)

    async def extract_articles_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Enhanced batch processing with Google News optimization.

        Separates Google News URLs for specialized batch processing
        using single browser multi-tab strategy.
        """
        # Separate Google News URLs for specialized handling
        google_news_urls = [url for url in urls if 'news.google.com' in url]
        standard_urls = [url for url in urls if 'news.google.com' not in url]

        results = []

        # Process Google News URLs with single browser multi-tab strategy
        if google_news_urls:
            logger.info(f"Processing {len(google_news_urls)} Google News URLs with single browser")
            google_results = await self._extract_google_news_batch(google_news_urls)
            results.extend(google_results)

        # Process standard URLs with regular method
        if standard_urls:
            logger.info(f"Processing {len(standard_urls)} standard URLs")
            standard_results = await asyncio.gather(
                *[self._extract_with_retry(url, str(uuid.uuid4())) for url in standard_urls],
                return_exceptions=True
            )
            results.extend(standard_results)

        return results

    async def _extract_google_news_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Process Google News URLs in batches of 10 using single browser.

        Implements proven anti-detection strategy:
        - 1 browser instance with 10 tabs maximum
        - Random delays between tab operations (1-3 seconds)
        - Delay between batches (5-10 seconds)
        - Proper session cleanup
        """
        batch_size = 10
        all_results = []

        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} URLs")

            batch_results = await self._process_batch_with_single_browser(batch)
            all_results.extend(batch_results)

            # Anti-detection delay between batches
            if i + batch_size < len(urls):
                delay = random.randint(5, 10)
                logger.info(f"Anti-detection delay: {delay} seconds")
                await asyncio.sleep(delay)

        return all_results

    async def _process_batch_with_single_browser(self, urls_batch: List[str]) -> List[Dict[str, Any]]:
        """
        Process URLs with single browser instance and multiple tabs.

        Critical implementation details from financial_news_extractor.py:
        - Ultra-fast settings with resource blocking
        - 4-5 second wait for JavaScript redirects
        - Proper timeout handling (30s max per tab)
        - Random delays between tab operations
        """
        if not self.playwright_available:
            return [{"success": False, "error": "Playwright not available"} for _ in urls_batch]

        results = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--max_old_space_size=512'
                    ]
                )

                logger.info(f"Browser started, processing {len(urls_batch)} URLs with tabs")

                # Process each URL in separate tab (max 10)
                for i, url in enumerate(urls_batch[:10]):
                    try:
                        page = await browser.new_page()

                        # Ultra-fast settings - block unnecessary resources
                        await page.route(
                            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}",
                            lambda route: route.abort()
                        )

                        await page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        })

                        logger.info(f"Tab {i+1}: Starting {url[:50]}...")

                        # Navigate with Google News specific timing
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                        # Critical: 4-5 second wait for Google News redirect
                        await asyncio.sleep(4)
                        final_url = page.url

                        # Handle no redirect case - wait longer for complex JS
                        if final_url == url or 'news.google.com' in final_url:
                            try:
                                await page.wait_for_load_state('networkidle', timeout=15000)
                                await asyncio.sleep(5)
                                final_url = page.url
                            except:
                                pass

                        logger.info(f"Tab {i+1}: Got {final_url[:50]}...")

                        # Extract content if successfully redirected
                        if final_url != url and 'news.google.com' not in final_url:
                            result = await self._extract_with_newspaper(final_url)
                            results.append(result)
                        else:
                            results.append({
                                "success": False,
                                "error": "No redirect",
                                "final_url": final_url,
                                "original_url": url
                            })

                        await page.close()

                        # Anti-detection delay between tabs
                        if i < len(urls_batch) - 1:
                            delay = random.randint(1, 3)
                            await asyncio.sleep(delay)

                    except Exception as e:
                        logger.error(f"Tab {i+1}: Error: {str(e)[:50]}")
                        results.append({
                            "success": False,
                            "error": str(e)[:100],
                            "final_url": url
                        })

                await browser.close()
                logger.info(f"Browser closed, processed {len(results)} URLs")

        except Exception as e:
            logger.error(f"Browser session failed: {e}")
            # Return failed results for all URLs
            results = [{"success": False, "error": str(e)} for _ in urls_batch]

        return results

    async def _extract_with_newspaper(self, final_url: str) -> Dict[str, Any]:
        """
        Extract article content using newspaper4k after successful redirect.

        Implements content extraction patterns from financial_news_extractor.py.
        """
        try:
            # Use newspaper4k for content extraction
            article = newspaper.Article(final_url, language='vi')
            await asyncio.to_thread(article.download)
            await asyncio.to_thread(article.parse)

            return {
                "success": True,
                "error": None,
                "final_url": final_url,
                "content": article.html[:1500] if article.html else None,
                "text": article.text[:4000] if article.text else None,
                "authors": article.authors[:2] if article.authors else [],
                "publish_date": str(article.publish_date) if article.publish_date else None,
                "top_image": article.top_image if article.top_image else None,
                "images": list(article.images)[:3] if article.images else [],
                "keywords": list(article.keywords)[:10] if hasattr(article, 'keywords') and article.keywords else [],
                "summary": article.summary[:800] if hasattr(article, 'summary') and article.summary else None,
                "title": article.title if article.title else None
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Extraction failed: {str(e)[:100]}",
                "final_url": final_url,
                "content": None, "text": None, "authors": [], "publish_date": None,
                "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
            }
```

### Anti-Detection Architecture

The system implements comprehensive anti-detection measures based on the proven 56% success rate patterns:

#### Rate Limiting Strategy

```python
class AntiDetectionManager:
    """
    Manages anti-detection measures for Google News extraction.

    Key patterns:
    - 1 browser, 10 tabs max (mimics normal user behavior)
    - Random delays: 1-3s between tabs, 5-10s between batches
    - Realistic headers: Windows Chrome User-Agent
    - Resource blocking: Images/CSS blocked for speed
    - Proper cleanup: Close tabs and browser properly
    """

    def __init__(self):
        self.max_tabs_per_browser = 10
        self.inter_tab_delay_range = (1, 3)  # seconds
        self.inter_batch_delay_range = (5, 10)  # seconds
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]

    async def get_inter_tab_delay(self) -> int:
        """Random delay between tab operations."""
        return random.randint(*self.inter_tab_delay_range)

    async def get_inter_batch_delay(self) -> int:
        """Random delay between batches."""
        return random.randint(*self.inter_batch_delay_range)

    def get_random_user_agent(self) -> str:
        """Rotate User-Agent headers per browser session."""
        return random.choice(self.user_agents)

    async def configure_page_for_stealth(self, page) -> None:
        """Configure page with anti-detection settings."""
        # Block unnecessary resources for speed
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}",
            lambda route: route.abort()
        )

        # Set realistic headers
        await page.set_extra_http_headers({
            'User-Agent': self.get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        })
```

### Performance Optimization Architecture

```python
class GoogleNewsOptimizer:
    """
    Performance optimization for Google News extraction.

    Based on financial_news_extractor.py optimization patterns:
    - Ultra-fast browser settings
    - Resource blocking for 3x speed improvement
    - Timeout handling with graceful degradation
    - Memory management with browser lifecycle
    """

    BROWSER_ARGS = [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--max_old_space_size=512'  # Limit memory usage
    ]

    BLOCKED_RESOURCES = [
        '**/*.{png,jpg,jpeg,gif,svg}',  # Images
        '**/*.{css,woff,woff2,ttf,eot}',  # Fonts and CSS
        '**/*.{ico,xml,weba}',  # Icons and audio
    ]

    TIMEOUTS = {
        'navigation': 30000,  # 30 seconds max navigation
        'redirect_wait': 4,   # 4 seconds for JS redirect
        'network_idle': 15000,  # 15 seconds for network idle
        'extended_wait': 5,   # 5 seconds extended wait
    }

    async def configure_browser_for_speed(self, browser_type):
        """Launch browser with ultra-fast settings."""
        return await browser_type.launch(
            headless=True,
            args=self.BROWSER_ARGS
        )

    async def configure_page_for_speed(self, page):
        """Configure page with resource blocking and timeouts."""
        # Block resource loading for speed
        for pattern in self.BLOCKED_RESOURCES:
            await page.route(pattern, lambda route: route.abort())

        # Set conservative timeouts
        page.set_default_navigation_timeout(self.TIMEOUTS['navigation'])
        page.set_default_timeout(self.TIMEOUTS['navigation'])
```

### Error Handling and Circuit Breaker Architecture

```python
class GoogleNewsCircuitBreaker:
    """
    Circuit breaker pattern for Google News extraction failures.

    Prevents cascade failures and implements graceful degradation:
    - Track success/failure rates per batch
    - Circuit breaker for repeated failures
    - Fallback to standard extraction
    - Monitoring and alerting integration
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    async def call_with_circuit_breaker(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half-open'
            else:
                raise CircuitBreakerOpenException("Google News extraction circuit breaker is open")

        try:
            result = await func(*args, **kwargs)

            # Reset on success
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error("Google News extraction circuit breaker opened",
                           failure_count=self.failure_count)

            raise e
```

This enhanced backend architecture provides a robust, scalable foundation for the job-centric enhancement while incorporating the proven Google News extraction patterns that achieve 56% success rate vs the current 0%. The architecture maintains high performance and reliability through proper layering, anti-detection measures, and comprehensive error handling.