"""Pydantic schemas for Category API requests and responses.

This module defines the data validation schemas used by the Category API endpoints
for request validation and response formatting.

Key Features:
- Request validation with field constraints
- Response formatting with proper types
- Field validation for keywords and names
- Error response schemas
- Consistent datetime formatting

Example:
    Using schemas for API validation:
    
    ```python
    from src.api.schemas.category import CreateCategoryRequest, CategoryResponse
    
    # Validate request data
    request_data = {
        "name": "Technology",
        "keywords": ["python", "javascript"],
        "exclude_keywords": ["deprecated"],
        "is_active": True
    }
    
    # This will raise ValidationError if invalid
    validated_request = CreateCategoryRequest(**request_data)
    
    # Format response data
    response = CategoryResponse(
        id=category.id,
        name=category.name,
        keywords=category.keywords,
        exclude_keywords=category.exclude_keywords,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at
    )
    ```
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator


class CreateCategoryRequest(BaseModel):
    """Schema for creating a new category."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Category name (must be unique)",
        example="Technology"
    )
    
    keywords: List[str] = Field(
        ...,
        min_items=1,
        max_items=20,
        description="Keywords for search (1-20 items)",
        example=["python", "javascript", "artificial intelligence"]
    )
    
    exclude_keywords: Optional[List[str]] = Field(
        None,
        max_items=20,
        description="Keywords to exclude from results",
        example=["deprecated", "old"]
    )
    
    is_active: bool = Field(
        True,
        description="Whether category is active for crawling",
        example=True
    )

    language: str = Field(
        "vi",
        min_length=2,
        max_length=5,
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Language code for Google News search (e.g., 'vi', 'en', 'zh-CN')",
        example="vi"
    )

    country: str = Field(
        "VN",
        min_length=2,
        max_length=5,
        pattern="^[A-Z]{2}$",
        description="Country code for Google News search (e.g., 'VN', 'US', 'GB')",
        example="VN"
    )

    crawl_period: Optional[str] = Field(
        None,
        description="Time period for scheduled crawls. Must be one of GNews supported values: 1h, 2h, 6h, 12h, 1d, 2d, 7d, 1m, 3m, 6m, 1y",
        example="7d"
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate category name."""
        if not v or not v.strip():
            raise ValueError('Category name cannot be empty')
        
        # Check for invalid characters
        if any(char in v for char in ['<', '>', '&', '"', "'"]):
            raise ValueError('Category name contains invalid characters')
        
        return v.strip()
    
    @validator('keywords')
    def validate_keywords(cls, v):
        """Validate keywords list."""
        if not v:
            raise ValueError('Keywords list cannot be empty')
        
        # Clean and filter keywords
        cleaned = [kw.strip() for kw in v if kw.strip()]
        
        if not cleaned:
            raise ValueError('At least one valid keyword is required')
        
        # Check individual keyword length
        for kw in cleaned:
            if len(kw) > 100:
                raise ValueError(f'Keyword "{kw}" exceeds maximum length of 100 characters')
        
        # Check for duplicates
        if len(cleaned) != len(set(cleaned)):
            raise ValueError('Duplicate keywords are not allowed')
        
        return cleaned
    
    @validator('exclude_keywords')
    def validate_exclude_keywords(cls, v):
        """Validate exclude keywords list."""
        if v is None:
            return []

        # Clean and filter keywords
        cleaned = [kw.strip() for kw in v if kw.strip()]

        # Check individual keyword length
        for kw in cleaned:
            if len(kw) > 100:
                raise ValueError(f'Exclude keyword "{kw}" exceeds maximum length of 100 characters')

        # Check for duplicates
        if len(cleaned) != len(set(cleaned)):
            raise ValueError('Duplicate exclude keywords are not allowed')

        return cleaned

    @validator('crawl_period')
    def validate_crawl_period(cls, v):
        """Validate crawl_period against GNews supported values."""
        if v is None:
            return v

        # GNews supported period values (tested and confirmed)
        VALID_PERIODS = ['1h', '2h', '6h', '12h', '1d', '2d', '7d', '1m', '3m', '6m', '1y']

        if v not in VALID_PERIODS:
            raise ValueError(
                f"crawl_period must be one of: {', '.join(VALID_PERIODS)}. "
                f"Got: '{v}'"
            )

        return v


class UpdateCategoryRequest(BaseModel):
    """Schema for updating an existing category."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="New category name",
        example="Updated Technology"
    )
    
    keywords: Optional[List[str]] = Field(
        None,
        min_items=1,
        max_items=20,
        description="New keywords list",
        example=["python", "javascript", "machine learning"]
    )
    
    exclude_keywords: Optional[List[str]] = Field(
        None,
        max_items=20,
        description="New exclude keywords list",
        example=["legacy", "deprecated"]
    )
    
    is_active: Optional[bool] = Field(
        None,
        description="New active status",
        example=True
    )

    language: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Language code for Google News search (e.g., 'vi', 'en', 'zh-CN')",
        example="vi"
    )

    country: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        pattern="^[A-Z]{2}$",
        description="Country code for Google News search (e.g., 'VN', 'US', 'GB')",
        example="VN"
    )

    crawl_period: Optional[str] = Field(
        None,
        description="Time period for scheduled crawls. Must be one of GNews supported values: 1h, 2h, 6h, 12h, 1d, 2d, 7d, 1m, 3m, 6m, 1y",
        example="7d"
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate category name."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Category name cannot be empty')
            
            # Check for invalid characters
            if any(char in v for char in ['<', '>', '&', '"', "'"]):
                raise ValueError('Category name contains invalid characters')
            
            return v.strip()
        return v
    
    @validator('keywords')
    def validate_keywords(cls, v):
        """Validate keywords list."""
        if v is not None:
            if not v:
                raise ValueError('Keywords list cannot be empty')
            
            # Clean and filter keywords
            cleaned = [kw.strip() for kw in v if kw.strip()]
            
            if not cleaned:
                raise ValueError('At least one valid keyword is required')
            
            # Check individual keyword length
            for kw in cleaned:
                if len(kw) > 100:
                    raise ValueError(f'Keyword "{kw}" exceeds maximum length of 100 characters')
            
            # Check for duplicates
            if len(cleaned) != len(set(cleaned)):
                raise ValueError('Duplicate keywords are not allowed')
            
            return cleaned
        return v
    
    @validator('exclude_keywords')
    def validate_exclude_keywords(cls, v):
        """Validate exclude keywords list."""
        if v is not None:
            # Clean and filter keywords
            cleaned = [kw.strip() for kw in v if kw.strip()]

            # Check individual keyword length
            for kw in cleaned:
                if len(kw) > 100:
                    raise ValueError(f'Exclude keyword "{kw}" exceeds maximum length of 100 characters')

            # Check for duplicates
            if len(cleaned) != len(set(cleaned)):
                raise ValueError('Duplicate exclude keywords are not allowed')

            return cleaned
        return v

    @validator('crawl_period')
    def validate_crawl_period(cls, v):
        """Validate crawl_period against GNews supported values."""
        if v is None:
            return v

        # GNews supported period values (tested and confirmed)
        VALID_PERIODS = ['1h', '2h', '6h', '12h', '1d', '2d', '7d', '1m', '3m', '6m', '1y']

        if v not in VALID_PERIODS:
            raise ValueError(
                f"crawl_period must be one of: {', '.join(VALID_PERIODS)}. "
                f"Got: '{v}'"
            )

        return v


class CategoryResponse(BaseModel):
    """Schema for category API responses."""
    
    id: UUID = Field(
        ...,
        description="Category unique identifier",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    
    name: str = Field(
        ...,
        description="Category name",
        example="Technology"
    )
    
    keywords: List[str] = Field(
        ...,
        description="List of keywords for search",
        example=["python", "javascript", "artificial intelligence"]
    )
    
    exclude_keywords: List[str] = Field(
        ...,
        description="List of keywords to exclude",
        example=["deprecated", "legacy"]
    )
    
    is_active: bool = Field(
        ...,
        description="Whether category is active",
        example=True
    )

    language: str = Field(
        "vi",
        description="Language code for Google News search",
        example="vi"
    )

    country: str = Field(
        "VN",
        description="Country code for Google News search",
        example="VN"
    )
    
    schedule_enabled: Optional[bool] = Field(
        False,
        description="Whether auto-crawl schedule is enabled",
        example=False
    )

    schedule_interval_minutes: Optional[int] = Field(
        None,
        description="Schedule interval in minutes",
        example=60
    )

    last_scheduled_run_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last scheduled crawl",
        example="2025-09-11T14:00:00Z"
    )

    next_scheduled_run_at: Optional[datetime] = Field(
        None,
        description="Timestamp of next scheduled crawl",
        example="2025-09-11T15:00:00Z"
    )

    crawl_period: Optional[str] = Field(
        None,
        description="Time period for scheduled crawls",
        example="2h"
    )

    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
        example="2025-09-11T10:30:00Z"
    )

    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
        example="2025-09-11T15:45:00Z"
    )

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda uuid: str(uuid)
        }


class CategoryListResponse(BaseModel):
    """Schema for category list API responses."""
    
    categories: List[CategoryResponse] = Field(
        ...,
        description="List of categories"
    )
    
    total: int = Field(
        ...,
        description="Total number of categories",
        example=25
    )
    
    active_count: int = Field(
        ...,
        description="Number of active categories",
        example=20
    )


class CategoryWithStatsResponse(CategoryResponse):
    """Schema for category response with article statistics."""
    
    article_count: int = Field(
        ...,
        description="Number of articles in this category",
        example=150
    )


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    
    error: str = Field(
        ...,
        description="Error message",
        example="Category with name 'Technology' already exists"
    )
    
    error_type: str = Field(
        ...,
        description="Type of error",
        example="DuplicateCategoryNameError"
    )
    
    details: Optional[dict] = Field(
        None,
        description="Additional error details",
        example={"field": "name", "value": "Technology"}
    )


class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses."""

    error: str = Field(
        ...,
        description="Error message",
        example="Validation failed"
    )

    errors: List[dict] = Field(
        ...,
        description="List of validation errors",
        example=[
            {
                "field": "keywords",
                "message": "At least one keyword is required",
                "type": "value_error"
            }
        ]
    )


class UpdateScheduleConfigRequest(BaseModel):
    """Schema for updating category schedule configuration."""

    enabled: bool = Field(
        ...,
        description="Enable or disable automatic scheduling",
        example=True
    )

    interval_minutes: Optional[int] = Field(
        None,
        description="Schedule interval in minutes (1, 5, 15, 30, 60, or 1440)",
        example=30
    )

    @validator('interval_minutes')
    def validate_interval(cls, v, values):
        """Validate schedule interval."""
        if values.get('enabled') and v is None:
            raise ValueError('interval_minutes is required when enabled=true')

        if v is not None and v not in [1, 5, 15, 30, 60, 1440]:
            raise ValueError('interval_minutes must be one of: 1, 5, 15, 30, 60, or 1440')

        return v


class ScheduleConfigResponse(BaseModel):
    """Schema for schedule configuration response."""

    category_id: UUID = Field(
        ...,
        description="Category ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )

    category_name: str = Field(
        ...,
        description="Category name",
        example="Technology"
    )

    schedule_enabled: bool = Field(
        ...,
        description="Whether schedule is enabled",
        example=True
    )

    schedule_interval_minutes: Optional[int] = Field(
        None,
        description="Schedule interval in minutes",
        example=30
    )

    schedule_display: str = Field(
        ...,
        description="Human-readable schedule interval",
        example="30 minutes"
    )

    last_scheduled_run_at: Optional[datetime] = Field(
        None,
        description="Last scheduled run timestamp",
        example="2025-10-02T10:30:00Z"
    )

    next_scheduled_run_at: Optional[datetime] = Field(
        None,
        description="Next scheduled run timestamp",
        example="2025-10-02T11:00:00Z"
    )

    next_run_display: Optional[str] = Field(
        None,
        description="Human-readable next run time",
        example="in 28 minutes"
    )

    class Config:
        from_attributes = True


class ScheduleCapacityResponse(BaseModel):
    """Schema for schedule capacity check response."""

    total_scheduled_categories: int = Field(
        ...,
        description="Total number of categories with enabled schedules",
        example=5
    )

    estimated_jobs_per_hour: int = Field(
        ...,
        description="Estimated jobs per hour based on schedules",
        example=30
    )

    capacity_status: str = Field(
        ...,
        description="Capacity status: 'normal', 'warning', or 'critical'",
        example="normal"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="List of warning messages if capacity is high",
        example=[]
    )

    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for capacity management",
        example=["Consider increasing intervals for some categories"]
    )