"""CrawlJob repository for managing job scheduling and tracking operations.

This module provides comprehensive database operations for managing crawl jobs,
including creation, status tracking, metrics, and cleanup operations.

The repository follows async/await patterns with proper transaction management
and includes specialized methods for job scheduling workflows.

Example:
    Basic job operations:
    
    ```python
    job_repo = CrawlJobRepository()
    
    # Create a new job
    job = await job_repo.create_job(category_id=category_uuid)
    
    # Update job status
    await job_repo.update_status(
        job_id=job.id,
        status="running",
        started_at=datetime.utcnow()
    )
    
    # Get active jobs
    active_jobs = await job_repo.get_active_jobs()
    ```
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from src.database.models.category import Category
from src.database.repositories.base import BaseRepository
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class CrawlJobRepository(BaseRepository[CrawlJob]):
    """Repository for managing crawl job operations."""
    
    model_class = CrawlJob
    
    async def create_job(
        self,
        category_id: UUID,
        priority: int = 0,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CrawlJob:
        """Create a new crawl job with initial pending status.
        
        Args:
            category_id: UUID of the category to crawl
            priority: Job execution priority (higher = more priority)
            correlation_id: Optional correlation ID for tracking
            metadata: Optional additional metadata
            
        Returns:
            Created CrawlJob instance
            
        Raises:
            Exception: If job creation fails
        """
        job_data = {
            "category_id": category_id,
            "status": CrawlJobStatus.PENDING,
            "priority": priority,
            "correlation_id": correlation_id,
            "metadata": metadata or {}
        }
        
        async with get_db_session() as session:
            async with session.begin():
                try:
                    job = CrawlJob(**job_data)
                    session.add(job)
                    await session.flush()
                    await session.refresh(job)
                    
                    logger.info(f"Created new crawl job", extra={
                        "job_id": str(job.id),
                        "category_id": str(category_id),
                        "priority": priority,
                        "correlation_id": correlation_id
                    })
                    
                    return job
                except Exception as e:
                    logger.error(f"Failed to create crawl job for category {category_id}: {e}")
                    raise
    
    async def update_status(
        self,
        job_id: UUID,
        status: CrawlJobStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        celery_task_id: Optional[str] = None,
        articles_found: Optional[int] = None,
        articles_saved: Optional[int] = None,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Update job status and related metadata.
        
        Args:
            job_id: UUID of the job to update
            status: New job status
            started_at: When job execution started
            completed_at: When job finished (success or failure)
            celery_task_id: Celery task ID for tracking
            articles_found: Number of articles discovered during crawl
            articles_saved: Number of articles successfully saved
            error_message: Error details if job failed
            retry_count: Number of retry attempts
            correlation_id: Correlation ID for tracking
            
        Returns:
            True if job was updated, False if not found
            
        Raises:
            Exception: If update fails
        """
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Add optional fields if provided
        if started_at is not None:
            update_data["started_at"] = started_at
        if completed_at is not None:
            update_data["completed_at"] = completed_at
        if celery_task_id is not None:
            update_data["celery_task_id"] = celery_task_id
        if articles_found is not None:
            update_data["articles_found"] = articles_found
        if articles_saved is not None:
            update_data["articles_saved"] = articles_saved
        if error_message is not None:
            update_data["error_message"] = error_message
        if retry_count is not None:
            update_data["retry_count"] = retry_count
        if correlation_id is not None:
            update_data["correlation_id"] = correlation_id
        
        async with get_db_session() as session:
            async with session.begin():
                try:
                    query = (
                        update(CrawlJob)
                        .where(CrawlJob.id == job_id)
                        .values(**update_data)
                        .execution_options(synchronize_session="fetch")
                    )
                    
                    result = await session.execute(query)
                    
                    if result.rowcount > 0:
                        logger.info(f"Updated job status", extra={
                            "job_id": str(job_id),
                            "status": status.value,
                            "articles_found": articles_found,
                            "articles_saved": articles_saved,
                            "correlation_id": correlation_id
                        })
                        return True
                    else:
                        logger.warning(f"Job not found for status update", extra={
                            "job_id": str(job_id),
                            "status": status.value
                        })
                        return False
                        
                except Exception as e:
                    logger.error(f"Failed to update job status: {e}", extra={
                        "job_id": str(job_id),
                        "status": status.value
                    })
                    raise
    
    async def get_active_jobs(self, limit: int = 100) -> List[CrawlJob]:
        """Get currently running or pending jobs.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of active jobs ordered by priority (desc) then created_at (asc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.status.in_([CrawlJobStatus.PENDING, CrawlJobStatus.RUNNING]))
                .order_by(desc(CrawlJob.priority), asc(CrawlJob.created_at))
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_pending_jobs(self, limit: int = 50) -> List[CrawlJob]:
        """Get jobs that are pending execution.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of pending jobs ordered by priority (desc) then created_at (asc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.status == CrawlJobStatus.PENDING)
                .order_by(desc(CrawlJob.priority), asc(CrawlJob.created_at))
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_running_jobs(self, limit: int = 50) -> List[CrawlJob]:
        """Get jobs that are currently running.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of running jobs ordered by started_at (asc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.status == CrawlJobStatus.RUNNING)
                .order_by(asc(CrawlJob.started_at))
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_failed_jobs(
        self,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[CrawlJob]:
        """Get jobs that failed for retry analysis.
        
        Args:
            since: Only return failures since this datetime
            limit: Maximum number of jobs to return
            
        Returns:
            List of failed jobs ordered by completed_at (desc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.status == CrawlJobStatus.FAILED)
            )
            
            if since:
                query = query.where(CrawlJob.completed_at >= since)
            
            query = query.order_by(desc(CrawlJob.completed_at)).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_completed_jobs(
        self,
        category_id: Optional[UUID] = None,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[CrawlJob]:
        """Get successfully completed jobs.
        
        Args:
            category_id: Filter by specific category
            since: Only return jobs completed since this datetime
            limit: Maximum number of jobs to return
            
        Returns:
            List of completed jobs ordered by completed_at (desc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.status == CrawlJobStatus.COMPLETED)
            )
            
            if category_id:
                query = query.where(CrawlJob.category_id == category_id)
            
            if since:
                query = query.where(CrawlJob.completed_at >= since)
            
            query = query.order_by(desc(CrawlJob.completed_at)).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_job_by_celery_id(self, celery_task_id: str) -> Optional[CrawlJob]:
        """Get job by its Celery task ID.
        
        Args:
            celery_task_id: Celery task ID to search for
            
        Returns:
            CrawlJob instance if found, None otherwise
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.celery_task_id == celery_task_id)
            )
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_job_statistics(
        self,
        category_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get job execution statistics for monitoring.
        
        Args:
            category_id: Filter by specific category
            from_date: Start date for statistics
            to_date: End date for statistics
            
        Returns:
            Dictionary containing job statistics
        """
        async with get_db_session() as session:
            base_query = select(CrawlJob)
            
            if category_id:
                base_query = base_query.where(CrawlJob.category_id == category_id)
            
            if from_date:
                base_query = base_query.where(CrawlJob.created_at >= from_date)
            
            if to_date:
                base_query = base_query.where(CrawlJob.created_at <= to_date)
            
            # Count jobs by status
            status_counts = {}
            for status in CrawlJobStatus:
                query = select(func.count()).select_from(
                    base_query.where(CrawlJob.status == status).subquery()
                )
                result = await session.execute(query)
                status_counts[status.value] = result.scalar() or 0
            
            # Get total articles metrics for completed jobs
            completed_query = base_query.where(CrawlJob.status == CrawlJobStatus.COMPLETED)
            
            total_articles_query = select(
                func.sum(CrawlJob.articles_found),
                func.sum(CrawlJob.articles_saved),
                func.avg(CrawlJob.articles_found),
                func.avg(CrawlJob.articles_saved)
            ).select_from(completed_query.subquery())
            
            result = await session.execute(total_articles_query)
            metrics = result.first()
            
            # Get average job duration for completed jobs
            duration_query = select(
                func.avg(
                    func.extract('epoch', CrawlJob.completed_at - CrawlJob.started_at)
                )
            ).select_from(
                completed_query.where(
                    and_(CrawlJob.started_at.is_not(None), CrawlJob.completed_at.is_not(None))
                ).subquery()
            )
            
            duration_result = await session.execute(duration_query)
            avg_duration = duration_result.scalar()
            
            return {
                "status_counts": status_counts,
                "total_articles_found": int(metrics[0] or 0),
                "total_articles_saved": int(metrics[1] or 0),
                "avg_articles_found": float(metrics[2] or 0),
                "avg_articles_saved": float(metrics[3] or 0),
                "avg_duration_seconds": float(avg_duration or 0),
                "success_rate": (
                    float(metrics[1] / metrics[0]) if metrics[0] and metrics[0] > 0 else 0.0
                ),
                "category_id": str(category_id) if category_id else None,
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """Remove completed/failed jobs older than specified days.
        
        Args:
            days_old: Age threshold in days for job cleanup
            
        Returns:
            Number of jobs cleaned up
            
        Raises:
            Exception: If cleanup fails
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        async with get_db_session() as session:
            async with session.begin():
                try:
                    query = delete(CrawlJob).where(
                        and_(
                            CrawlJob.status.in_([CrawlJobStatus.COMPLETED, CrawlJobStatus.FAILED]),
                            CrawlJob.completed_at < cutoff_date
                        )
                    )
                    
                    result = await session.execute(query)
                    cleaned_count = result.rowcount
                    
                    logger.info(f"Cleaned up {cleaned_count} old jobs", extra={
                        "days_old": days_old,
                        "cutoff_date": cutoff_date.isoformat(),
                        "cleaned_count": cleaned_count
                    })
                    
                    return cleaned_count
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup old jobs: {e}")
                    raise
    
    async def get_stuck_jobs(self, stuck_threshold_hours: int = 2) -> List[CrawlJob]:
        """Get jobs that appear to be stuck in running state.
        
        Args:
            stuck_threshold_hours: Hours after which a running job is considered stuck
            
        Returns:
            List of potentially stuck jobs
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=stuck_threshold_hours)
        
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(
                    and_(
                        CrawlJob.status == CrawlJobStatus.RUNNING,
                        CrawlJob.started_at < cutoff_time
                    )
                )
                .order_by(asc(CrawlJob.started_at))
            )
            
            result = await session.execute(query)
            stuck_jobs = list(result.scalars().all())
            
            if stuck_jobs:
                logger.warning(f"Found {len(stuck_jobs)} potentially stuck jobs", extra={
                    "stuck_threshold_hours": stuck_threshold_hours,
                    "stuck_job_ids": [str(job.id) for job in stuck_jobs]
                })
            
            return stuck_jobs
    
    async def reset_stuck_jobs(self, stuck_threshold_hours: int = 2) -> int:
        """Reset stuck jobs back to pending status.
        
        Args:
            stuck_threshold_hours: Hours after which a running job is considered stuck
            
        Returns:
            Number of jobs reset
            
        Raises:
            Exception: If reset fails
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=stuck_threshold_hours)
        
        async with get_db_session() as session:
            async with session.begin():
                try:
                    update_data = {
                        "status": CrawlJobStatus.PENDING,
                        "started_at": None,
                        "celery_task_id": None,
                        "error_message": f"Reset due to being stuck for over {stuck_threshold_hours} hours",
                        "retry_count": CrawlJob.retry_count + 1,
                        "updated_at": datetime.now(timezone.utc)
                    }
                    
                    query = (
                        update(CrawlJob)
                        .where(
                            and_(
                                CrawlJob.status == CrawlJobStatus.RUNNING,
                                CrawlJob.started_at < cutoff_time
                            )
                        )
                        .values(**update_data)
                        .execution_options(synchronize_session="fetch")
                    )
                    
                    result = await session.execute(query)
                    reset_count = result.rowcount
                    
                    logger.warning(f"Reset {reset_count} stuck jobs", extra={
                        "stuck_threshold_hours": stuck_threshold_hours,
                        "cutoff_time": cutoff_time.isoformat(),
                        "reset_count": reset_count
                    })
                    
                    return reset_count
                    
                except Exception as e:
                    logger.error(f"Failed to reset stuck jobs: {e}")
                    raise
    
    async def get_jobs_by_category(
        self,
        category_id: UUID,
        status: Optional[CrawlJobStatus] = None,
        limit: int = 50
    ) -> List[CrawlJob]:
        """Get jobs for a specific category.
        
        Args:
            category_id: Category UUID to filter by
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs for the category ordered by created_at (desc)
        """
        async with get_db_session() as session:
            query = (
                select(CrawlJob)
                .options(joinedload(CrawlJob.category))
                .where(CrawlJob.category_id == category_id)
            )
            
            if status:
                query = query.where(CrawlJob.status == status)
            
            query = query.order_by(desc(CrawlJob.created_at)).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())