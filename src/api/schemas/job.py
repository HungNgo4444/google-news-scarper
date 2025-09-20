"""Pydantic schemas for Job API requests and responses.

This module defines the data validation schemas used by the Jobs API endpoints
for request validation and response formatting.

Key Features:
- Request validation with field constraints
- Response formatting with proper types
- Status and priority validation
- Error response schemas
- Consistent datetime formatting

Example:
    Using schemas for API validation:

    ```python
    from src.api.schemas.job import CreateJobRequest, JobResponse

    # Validate request data
    request_data = {
        "category_id": "123e4567-e89b-12d3-a456-426614174000",
        "priority": 5
    }

    # This will raise ValidationError if invalid
    validated_request = CreateJobRequest(**request_data)

    # Format response data
    response = JobResponse(
        id=job.id,
        category_id=job.category_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at
    )
    ```
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, validator

from src.database.models.crawl_job import CrawlJobStatus


class CreateJobRequest(BaseModel):
    """Schema for creating a new crawl job."""

    category_id: UUID = Field(
        ...,
        description="Category UUID to crawl",
        example="123e4567-e89b-12d3-a456-426614174000"
    )

    priority: int = Field(
        0,
        ge=0,
        le=10,
        description="Job priority (0-10, higher = more priority)",
        example=5
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata for the job",
        example={"source": "manual_trigger", "user": "admin"}
    )

    @validator('metadata')
    def validate_metadata(cls, v):
        """Validate metadata dictionary."""
        if v is None:
            return {}

        # Check for reasonable size limit
        if len(str(v)) > 1000:
            raise ValueError('Metadata is too large (max 1000 characters)')

        return v


class PriorityUpdateRequest(BaseModel):
    """Schema for updating job priority (Run Now functionality)."""

    priority: int = Field(
        ...,
        ge=0,
        le=10,
        description="New priority value (0-10, higher = more urgent)",
        example=10
    )


class JobUpdateRequest(BaseModel):
    """Schema for updating job configuration."""

    priority: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Job priority (0-10, higher = more priority)",
        example=5
    )

    retry_count: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Number of retry attempts",
        example=3
    )

    job_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Job metadata updates",
        example={"source": "manual_update", "priority_reason": "urgent_news"}
    )

    @validator('job_metadata')
    def validate_job_metadata(cls, v):
        """Validate job metadata dictionary."""
        if v is None:
            return None

        # Check for reasonable size limit
        if len(str(v)) > 1000:
            raise ValueError('Job metadata is too large (max 1000 characters)')

        return v


class JobResponse(BaseModel):
    """Schema for job API responses."""

    id: UUID = Field(
        ...,
        description="Job unique identifier",
        example="123e4567-e89b-12d3-a456-426614174000"
    )

    category_id: UUID = Field(
        ...,
        description="Category UUID being crawled",
        example="123e4567-e89b-12d3-a456-426614174000"
    )

    category_name: str = Field(
        ...,
        description="Name of the category being crawled",
        example="Technology News"
    )

    status: CrawlJobStatus = Field(
        ...,
        description="Current job status",
        example="pending"
    )

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        """Convert string status to enum if needed."""
        if isinstance(v, str):
            return CrawlJobStatus(v)
        return v

    celery_task_id: Optional[str] = Field(
        None,
        description="Celery task ID if job is running",
        example="b7b8c2d5-4e5f-4a7b-8c9d-1e2f3a4b5c6d"
    )

    started_at: Optional[datetime] = Field(
        None,
        description="When job execution started",
        example="2025-09-14T10:30:00Z"
    )

    completed_at: Optional[datetime] = Field(
        None,
        description="When job finished",
        example="2025-09-14T10:45:00Z"
    )

    articles_found: int = Field(
        ...,
        description="Number of articles discovered",
        example=25
    )

    articles_saved: int = Field(
        ...,
        description="Number of articles successfully saved",
        example=20
    )

    error_message: Optional[str] = Field(
        None,
        description="Error message if job failed",
        example="Connection timeout"
    )

    retry_count: int = Field(
        ...,
        description="Number of retry attempts",
        example=0
    )

    priority: int = Field(
        ...,
        description="Job execution priority",
        example=5
    )

    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for tracking",
        example="job_123_456"
    )

    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
        example="2025-09-14T10:30:00Z"
    )

    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
        example="2025-09-14T10:45:00Z"
    )

    # Computed properties
    duration_seconds: Optional[int] = Field(
        None,
        description="Job duration in seconds (if finished)",
        example=900
    )

    success_rate: float = Field(
        ...,
        description="Success rate (articles_saved / articles_found)",
        example=0.8
    )

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda uuid: str(uuid)
        }


class JobListResponse(BaseModel):
    """Schema for job list API responses."""

    jobs: List[JobResponse] = Field(
        ...,
        description="List of jobs"
    )

    total: int = Field(
        ...,
        description="Total number of jobs",
        example=50
    )

    pending_count: int = Field(
        ...,
        description="Number of pending jobs",
        example=10
    )

    running_count: int = Field(
        ...,
        description="Number of running jobs",
        example=5
    )

    completed_count: int = Field(
        ...,
        description="Number of completed jobs",
        example=30
    )

    failed_count: int = Field(
        ...,
        description="Number of failed jobs",
        example=5
    )


class JobStatusResponse(BaseModel):
    """Schema for job status endpoint response."""

    id: UUID = Field(
        ...,
        description="Job unique identifier"
    )

    status: CrawlJobStatus = Field(
        ...,
        description="Current job status"
    )

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        """Convert string status to enum if needed."""
        if isinstance(v, str):
            return CrawlJobStatus(v)
        return v

    progress: Optional[Dict[str, Any]] = Field(
        None,
        description="Progress information if available",
        example={
            "articles_found": 10,
            "articles_processed": 8,
            "estimated_completion": "2025-09-14T10:45:00Z"
        }
    )

    error_message: Optional[str] = Field(
        None,
        description="Error message if job failed"
    )

    started_at: Optional[datetime] = Field(
        None,
        description="When job started"
    )

    completed_at: Optional[datetime] = Field(
        None,
        description="When job finished"
    )

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda uuid: str(uuid)
        }


class JobDeletionRequest(BaseModel):
    """Schema for job deletion with impact analysis."""

    force: bool = Field(
        False,
        description="Force deletion even if job is running",
        example=False
    )

    delete_articles: bool = Field(
        False,
        description="Also delete associated articles",
        example=False
    )


class JobDeletionResponse(BaseModel):
    """Schema for job deletion response with impact information."""

    job_id: UUID = Field(
        ...,
        description="ID of deleted job"
    )

    impact: Dict[str, Any] = Field(
        ...,
        description="Impact analysis of deletion",
        example={
            "articles_affected": 15,
            "articles_deleted": 0,
            "was_running": False
        }
    )

    message: str = Field(
        ...,
        description="Deletion confirmation message",
        example="Job deleted successfully"
    )

    deleted_at: datetime = Field(
        ...,
        description="When the job was deleted"
    )


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str = Field(
        ...,
        description="Error message",
        example="Job not found"
    )

    error_type: str = Field(
        ...,
        description="Type of error",
        example="NotFoundError"
    )

    correlation_id: Optional[str] = Field(
        None,
        description="Request correlation ID"
    )