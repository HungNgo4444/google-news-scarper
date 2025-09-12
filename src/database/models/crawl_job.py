from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import String, Integer, DateTime, Text, CheckConstraint, Index, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from .base import BaseModel


class CrawlJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlJob(BaseModel):
    __tablename__ = "crawl_jobs"
    
    # Foreign key to category
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Job status tracking
    status: Mapped[CrawlJobStatus] = mapped_column(
        SQLEnum(CrawlJobStatus),
        nullable=False,
        default=CrawlJobStatus.PENDING,
        index=True
    )
    
    # Celery task tracking
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        unique=True
    )
    
    # Job execution timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Job metrics and results
    articles_found: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    articles_saved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Job configuration
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True
    )
    
    # Additional metadata for job tracking
    job_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Job execution context
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    
    # Relationships
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="crawl_jobs"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint("articles_found >= 0", name="articles_found_non_negative"),
        CheckConstraint("articles_saved >= 0", name="articles_saved_non_negative"),
        CheckConstraint("articles_saved <= articles_found", name="articles_saved_not_exceed_found"),
        CheckConstraint("retry_count >= 0", name="retry_count_non_negative"),
        CheckConstraint("retry_count <= 10", name="retry_count_max_limit"),
        CheckConstraint(
            "(started_at IS NULL AND status = 'pending') OR (started_at IS NOT NULL AND status != 'pending')",
            name="started_at_status_consistency"
        ),
        CheckConstraint(
            "(completed_at IS NULL AND status IN ('pending', 'running')) OR (completed_at IS NOT NULL AND status IN ('completed', 'failed'))",
            name="completed_at_status_consistency"
        ),
        CheckConstraint(
            "(started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at)",
            name="completion_after_start"
        ),
        
        # Indexes for performance
        Index("idx_crawl_jobs_category_id", "category_id"),
        Index("idx_crawl_jobs_status", "status"),
        Index("idx_crawl_jobs_celery_task_id", "celery_task_id"),
        Index("idx_crawl_jobs_started_at", "started_at"),
        Index("idx_crawl_jobs_completed_at", "completed_at"),
        Index("idx_crawl_jobs_priority", "priority"),
        Index("idx_crawl_jobs_correlation_id", "correlation_id"),
        
        # Composite indexes for common queries
        Index("idx_crawl_jobs_category_status", "category_id", "status"),
        Index("idx_crawl_jobs_status_priority", "status", "priority"),
        Index("idx_crawl_jobs_status_created_at", "status", "created_at"),
        Index("idx_crawl_jobs_completed_at_status", "completed_at", "status"),
        
        # GIN index for job_metadata JSONB column
        Index("idx_crawl_jobs_job_metadata_gin", "job_metadata", postgresql_using="gin"),
    )
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate job duration in seconds if both started_at and completed_at are set"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    @property
    def is_finished(self) -> bool:
        """Check if job is in a finished state"""
        return self.status in (CrawlJobStatus.COMPLETED, CrawlJobStatus.FAILED)
    
    @property
    def is_running(self) -> bool:
        """Check if job is currently running"""
        return self.status == CrawlJobStatus.RUNNING
    
    @property
    def is_pending(self) -> bool:
        """Check if job is pending execution"""
        return self.status == CrawlJobStatus.PENDING
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as articles_saved / articles_found"""
        if self.articles_found == 0:
            return 0.0
        return self.articles_saved / self.articles_found
    
    def __repr__(self) -> str:
        return (
            f"<CrawlJob("
            f"id={self.id}, "
            f"category_id={self.category_id}, "
            f"status={self.status.value}, "
            f"articles_found={self.articles_found}, "
            f"articles_saved={self.articles_saved}, "
            f"duration={self.duration_seconds}s"
            f")>"
        )