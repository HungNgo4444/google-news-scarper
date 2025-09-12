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