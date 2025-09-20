from typing import List, Optional
from sqlalchemy import String, Boolean, CheckConstraint, Index, func
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
        Index("idx_categories_name", "name"),
        Index("idx_categories_is_active", "is_active"),
        Index("idx_categories_keywords_gin", "keywords", postgresql_using="gin"),
        Index("idx_categories_exclude_keywords_gin", "exclude_keywords", postgresql_using="gin"),
    )
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', active={self.is_active}, keywords_count={len(self.keywords) if self.keywords else 0})>"