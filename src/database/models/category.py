from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel


class Category(BaseModel):
    __tablename__ = "categories"
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    
    keywords: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )
    
    exclude_keywords: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=func.jsonb_build_array()
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    # Language and country settings for Google News search
    language: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="vi",  # Vietnamese by default
        comment="Language code for Google News search (e.g., 'vi', 'en')"
    )

    country: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="VN",  # Vietnam by default
        comment="Country code for Google News search (e.g., 'VN', 'US')"
    )

    # Scheduling configuration
    schedule_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default='false',
        comment="Whether auto-crawl schedule is enabled"
    )

    schedule_interval_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Schedule interval in minutes (1, 5, 15, 30, 60, 1440)"
    )

    last_scheduled_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last scheduled crawl execution"
    )

    next_scheduled_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Timestamp of next scheduled crawl"
    )

    crawl_period: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Time period for scheduled crawls (e.g., '1h', '7d', '1m'). Format: number + unit (h=hours, d=days, m=months, w=weeks, y=years)"
    )

    # Relationships
    articles: Mapped[List["ArticleCategory"]] = relationship(
        "ArticleCategory",
        back_populates="category",
        cascade="all, delete-orphan"
    )
    
    crawl_jobs: Mapped[List["CrawlJob"]] = relationship(
        "CrawlJob",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="desc(CrawlJob.created_at)"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "jsonb_array_length(keywords) > 0",
            name="keywords_not_empty"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
        CheckConstraint(
            "schedule_interval_minutes IS NULL OR schedule_interval_minutes IN (1, 5, 15, 30, 60, 1440)",
            name="schedule_interval_valid"
        ),
        CheckConstraint(
            "(schedule_enabled = false) OR (schedule_enabled = true AND schedule_interval_minutes IS NOT NULL)",
            name="schedule_enabled_requires_interval"
        ),
        CheckConstraint(
            "crawl_period IS NULL OR crawl_period IN ('1h', '2h', '6h', '12h', '1d', '2d', '7d', '1m', '3m', '6m', '1y')",
            name="crawl_period_format_valid"
        ),
        Index("idx_categories_name", "name"),
        Index("idx_categories_is_active", "is_active"),
        Index("idx_categories_keywords_gin", "keywords", postgresql_using="gin"),
        Index("idx_categories_exclude_keywords_gin", "exclude_keywords", postgresql_using="gin"),
        Index("idx_categories_schedule_enabled", "schedule_enabled"),
    )
    
    @property
    def schedule_display(self) -> str:
        """Human-readable schedule interval"""
        if not self.schedule_enabled or not self.schedule_interval_minutes:
            return "Disabled"

        intervals = {
            1: "1 minute",
            5: "5 minutes",
            15: "15 minutes",
            30: "30 minutes",
            60: "1 hour",
            1440: "1 day"
        }
        return intervals.get(self.schedule_interval_minutes, f"{self.schedule_interval_minutes} minutes")

    @property
    def crawl_period_display(self) -> str:
        """Human-readable crawl period"""
        if not self.crawl_period:
            return "No limit"

        # Parse format like "2h" → "2 hours", "1m" → "1 month"
        import re
        match = re.match(r'^(\d+)([hdmwy])$', self.crawl_period)
        if match:
            num, unit = match.groups()
            unit_names = {
                'h': 'hour',
                'd': 'day',
                'm': 'month',
                'w': 'week',
                'y': 'year'
            }
            unit_name = unit_names[unit]
            return f"{num} {unit_name}{'s' if int(num) > 1 else ''}"
        return self.crawl_period

    @property
    def next_run_display(self) -> Optional[str]:
        """Human-readable next run time"""
        if not self.schedule_enabled or not self.next_scheduled_run_at:
            return None

        delta = self.next_scheduled_run_at - datetime.now(timezone.utc)

        if delta.total_seconds() < 0:
            return "Overdue"
        elif delta.total_seconds() < 60:
            return "in less than 1 minute"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"in {minutes} minute{'s' if minutes != 1 else ''}"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"in {hours} hour{'s' if hours != 1 else ''}"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"in {days} day{'s' if days != 1 else ''}"

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', active={self.is_active}, keywords_count={len(self.keywords) if self.keywords else 0})>"