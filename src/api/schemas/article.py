"""Article schemas for API requests and responses.

This module contains Pydantic models for article-related API operations including:
- Article response schemas with metadata
- Article listing with pagination
- Article search and filtering
- Article export functionality

All schemas include proper validation and documentation for API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class ArticleCategoryInfo(BaseModel):
    """Category information for an article."""

    id: str = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    relevance_score: float = Field(..., description="Relevance score for this category")


class ArticleResponse(BaseModel):
    """Response schema for article data with job-related metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str = Field(..., description="Article title")
    content: Optional[str] = Field(None, description="Full article content")
    author: Optional[str] = Field(None, description="Article author")
    publish_date: Optional[datetime] = Field(None, description="Article publication date")
    source_url: str = Field(..., description="Original article URL")
    image_url: Optional[str] = Field(None, description="Article image URL")
    url_hash: str = Field(..., description="SHA256 hash of the URL")
    content_hash: Optional[str] = Field(None, description="SHA256 hash of the content")
    last_seen: datetime = Field(..., description="Last time article was crawled")

    # Job-related fields
    crawl_job_id: Optional[UUID] = Field(None, description="ID of the crawl job that found this article")
    keywords_matched: Optional[List[str]] = Field(default_factory=list, description="Keywords that matched for this article")
    relevance_score: float = Field(0.0, description="Relevance score (0.0-1.0)")

    # Multi-category fields
    categories: Optional[List[ArticleCategoryInfo]] = Field(None, description="Categories this article belongs to")
    primary_category_id: Optional[str] = Field(None, description="Primary category ID (from crawl job)")

    # Base model fields
    created_at: datetime = Field(..., description="Article creation timestamp")
    updated_at: datetime = Field(..., description="Article last update timestamp")


class ArticleListResponse(BaseModel):
    """Response schema for paginated article listing."""

    articles: List[ArticleResponse] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles matching filters")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of articles per page")
    pages: int = Field(..., description="Total number of pages")


class ArticleSearchRequest(BaseModel):
    """Request schema for article search and filtering."""

    job_id: Optional[UUID] = Field(None, description="Filter by specific crawl job ID")
    category_id: Optional[UUID] = Field(None, description="Filter by category ID")
    search_query: Optional[str] = Field(None, description="Search in title and content")
    keywords: Optional[List[str]] = Field(None, description="Filter by matched keywords")
    min_relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum relevance score")
    from_date: Optional[datetime] = Field(None, description="Filter articles from this date")
    to_date: Optional[datetime] = Field(None, description="Filter articles until this date")
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Number of articles per page")


class ArticleExportRequest(BaseModel):
    """Request schema for article export functionality."""

    job_id: Optional[UUID] = Field(None, description="Export articles from specific job")
    category_id: Optional[UUID] = Field(None, description="Export articles from specific category")
    format: str = Field(..., pattern="^(json|csv|xlsx)$", description="Export format: json, csv, or xlsx")
    fields: Optional[List[str]] = Field(None, description="Specific fields to export (if not provided, exports all)")
    search_filters: Optional[ArticleSearchRequest] = Field(None, description="Additional search filters")


class ArticleExportResponse(BaseModel):
    """Response schema for article export operations."""

    export_id: str = Field(..., description="Unique export operation ID")
    status: str = Field(..., description="Export status: pending, processing, completed, failed")
    download_url: Optional[str] = Field(None, description="Download URL when export is completed")
    total_articles: int = Field(..., description="Total number of articles exported")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    created_at: datetime = Field(..., description="Export creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Download URL expiration time")


class ArticleStatsResponse(BaseModel):
    """Response schema for article statistics."""

    total_articles: int = Field(..., description="Total articles in database")
    articles_by_job: Dict[str, int] = Field(..., description="Article count by job ID")
    articles_by_category: Dict[str, int] = Field(..., description="Article count by category")
    recent_articles_count: int = Field(..., description="Articles found in last 24 hours")
    average_relevance_score: float = Field(..., description="Average relevance score")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: Dict[str, Any] = Field(..., description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request correlation ID")