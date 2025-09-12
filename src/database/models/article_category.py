from decimal import Decimal
from typing import Optional
import uuid
from sqlalchemy import ForeignKey, CheckConstraint, Index, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel


class ArticleCategory(BaseModel):
    __tablename__ = "article_categories"
    
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    relevance_score: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(3, 2),
        nullable=True,
        default=Decimal("1.0")
    )
    
    # Relationships
    article: Mapped["Article"] = relationship(
        "Article",
        back_populates="categories"
    )
    
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="articles"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0.0 AND relevance_score <= 1.0",
            name="valid_relevance_score"
        ),
        Index("idx_article_categories_article_id", "article_id"),
        Index("idx_article_categories_category_id", "category_id"),
        Index("idx_article_categories_composite", "article_id", "category_id", unique=True),
        Index("idx_article_categories_relevance", "relevance_score"),
    )
    
    def __repr__(self) -> str:
        return f"<ArticleCategory(article_id={self.article_id}, category_id={self.category_id}, relevance={self.relevance_score})>"