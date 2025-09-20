"""Sync job repository for Celery tasks."""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, update

from src.database.repositories.sync_base import SyncBaseRepository
from src.database.models.crawl_job import CrawlJob, CrawlJobStatus

logger = logging.getLogger(__name__)


class SyncCrawlJobRepository(SyncBaseRepository[CrawlJob]):
    """Sync job repository for Celery workers."""

    model_class = CrawlJob

    def update_status(
        self,
        job_id: UUID,
        status: CrawlJobStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        articles_found: Optional[int] = None,
        articles_saved: Optional[int] = None,
        error_message: Optional[str] = None,
        celery_task_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Update job status and metrics."""
        try:
            with self.get_session() as session:
                job = session.get(CrawlJob, job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return False

                # Update fields
                job.status = status
                job.updated_at = datetime.now(timezone.utc)

                if started_at is not None:
                    job.started_at = started_at
                if completed_at is not None:
                    job.completed_at = completed_at
                if articles_found is not None:
                    job.articles_found = articles_found
                if articles_saved is not None:
                    job.articles_saved = articles_saved
                if error_message is not None:
                    job.error_message = error_message
                if celery_task_id is not None:
                    job.celery_task_id = celery_task_id
                if correlation_id is not None:
                    job.correlation_id = correlation_id

                session.commit()

                logger.info(f"Updated job {job_id} status to {status}")
                return True

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False

    def get_pending_jobs(self, limit: int = 100) -> List[CrawlJob]:
        """Get pending jobs."""
        with self.get_session() as session:
            stmt = select(CrawlJob).where(
                CrawlJob.status == CrawlJobStatus.PENDING
            ).limit(limit)
            result = session.execute(stmt)
            return result.scalars().all()

    def get_running_jobs(self, limit: int = 100) -> List[CrawlJob]:
        """Get running jobs."""
        with self.get_session() as session:
            stmt = select(CrawlJob).where(
                CrawlJob.status == CrawlJobStatus.RUNNING
            ).limit(limit)
            result = session.execute(stmt)
            return result.scalars().all()