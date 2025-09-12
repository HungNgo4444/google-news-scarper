from datetime import datetime
from typing import Optional, List
import hashlib
from sqlalchemy import String, Text, DateTime, CheckConstraint, Index
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
    
    # Relationships
    categories: Mapped[List["ArticleCategory"]] = relationship(
        "ArticleCategory",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_empty"),
        CheckConstraint("length(url_hash) = 64", name="valid_url_hash"),
        CheckConstraint("content_hash IS NULL OR length(content_hash) = 64", name="valid_content_hash"),
        Index("idx_articles_created_at", "created_at"),
        Index("idx_articles_publish_date_desc", "publish_date", postgresql_using="btree"),
        Index("idx_articles_last_seen", "last_seen"),
        Index("idx_articles_title_gin", "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
        Index("idx_articles_content_gin", "content", postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
    )
    
    @staticmethod
    def generate_url_hash(url: str) -> str:
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    @staticmethod
    def generate_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:50]}...', url_hash='{self.url_hash[:8]}...')>"