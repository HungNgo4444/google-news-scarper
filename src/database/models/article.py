from datetime import datetime
from typing import Optional, List
import hashlib
import uuid
from sqlalchemy import String, Text, DateTime, CheckConstraint, Index, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel


class Article(BaseModel):
    __tablename__ = "articles"
    
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True
    )
    
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    author: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    publish_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    url_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True
    )
    
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )
    
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(),
        index=True
    )

    # Job tracking for article-job association
    crawl_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Article metadata for job-centric functionality
    keywords_matched: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=lambda: []
    )

    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True
    )

    # Relationships
    categories: Mapped[List["ArticleCategory"]] = relationship(
        "ArticleCategory",
        back_populates="article",
        cascade="all, delete-orphan"
    )

    crawl_job: Mapped[Optional["CrawlJob"]] = relationship(
        "CrawlJob",
        back_populates="articles"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_empty"),
        CheckConstraint("length(url_hash) = 64", name="valid_url_hash"),
        CheckConstraint("content_hash IS NULL OR length(content_hash) = 64", name="valid_content_hash"),
        CheckConstraint("relevance_score >= 0.0 AND relevance_score <= 1.0", name="valid_relevance_score"),
        Index("idx_articles_created_at", "created_at"),
        Index("idx_articles_publish_date_desc", "publish_date", postgresql_using="btree"),
        Index("idx_articles_last_seen", "last_seen"),
        Index("idx_articles_title_gin", "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
        Index("idx_articles_content_gin", "content", postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
        Index("idx_articles_crawl_job_id", "crawl_job_id"),
        Index("idx_articles_keywords_matched_gin", "keywords_matched", postgresql_using="gin"),
        Index("idx_articles_relevance_score", "relevance_score"),
    )
    
    @staticmethod
    def generate_url_hash(url: str) -> str:
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    @staticmethod
    def generate_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:50]}...', url_hash='{self.url_hash[:8]}...')>"