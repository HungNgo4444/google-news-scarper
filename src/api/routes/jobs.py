"""Jobs API routes for managing crawl job operations.

This module provides REST API endpoints for managing crawl jobs including:
- Creating new jobs
- Listing jobs with filters
- Getting job status
- Job monitoring and statistics

All endpoints use proper error handling, validation, and structured logging
with correlation IDs for request tracking.

Example:
    Using the jobs API:

    ```bash
    # Create a new job
    POST /api/v1/jobs
    {
        "category_id": "123e4567-e89b-12d3-a456-426614174000",
        "priority": 5
    }

    # List all jobs
    GET /api/v1/jobs

    # Get job status
    GET /api/v1/jobs/{job_id}/status
    ```
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import JSONResponse
import structlog

from src.api.schemas.job import (
    CreateJobRequest,
    JobResponse,
    JobListResponse,
    JobStatusResponse,
    PriorityUpdateRequest,
    JobUpdateRequest,
    JobDeletionRequest,
    JobDeletionResponse,
    ErrorResponse
)
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.category_repo import CategoryRepository
from src.database.models.crawl_job import CrawlJobStatus, CrawlJob
from src.core.scheduler.tasks import trigger_category_crawl_task
from src.shared.exceptions import (
    BaseAppException,
    DatabaseConnectionError,
    ValidationError,
    CategoryNotFoundError
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def get_job_repository() -> CrawlJobRepository:
    """Dependency to get CrawlJobRepository instance."""
    return CrawlJobRepository()


def get_category_repository() -> CategoryRepository:
    """Dependency to get CategoryRepository instance."""
    return CategoryRepository()


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    job_request: CreateJobRequest,
    request: Request,
    job_repo: CrawlJobRepository = Depends(get_job_repository),
    category_repo: CategoryRepository = Depends(get_category_repository)
) -> JobResponse:
    """Create a new crawl job for a category.

    This endpoint creates a new crawl job and triggers the background
    task to execute it. The job will be queued for processing.

    Args:
        job_request: Job creation request data
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency
        category_repo: Category repository dependency

    Returns:
        Created job data with status and tracking information

    Raises:
        HTTPException: If category not found or job creation fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Creating new job",
        correlation_id=correlation_id,
        category_id=str(job_request.category_id),
        priority=job_request.priority
    )

    try:
        # Verify category exists
        category = await category_repo.get_by_id(job_request.category_id)
        if not category:
            logger.warning(
                "Category not found for job creation",
                correlation_id=correlation_id,
                category_id=str(job_request.category_id)
            )
            raise HTTPException(
                status_code=404,
                detail=f"Category with ID {job_request.category_id} not found"
            )

        # Verify category is active
        if not category.is_active:
            logger.warning(
                "Attempted to create job for inactive category",
                correlation_id=correlation_id,
                category_id=str(job_request.category_id)
            )
            raise HTTPException(
                status_code=400,
                detail=f"Category '{category.name}' is not active"
            )

        # Create job record
        job = await job_repo.create_job(
            category_id=job_request.category_id,
            priority=job_request.priority,
            correlation_id=correlation_id,
            metadata=job_request.metadata
        )

        # Trigger background task
        task_result = trigger_category_crawl_task.delay(
            category_id=str(job_request.category_id),
            priority=job_request.priority,
            metadata=job_request.metadata
        )

        # Update job with Celery task ID
        await job_repo.update_status(
            job_id=job.id,
            status=CrawlJobStatus.PENDING,
            celery_task_id=task_result.id,
            correlation_id=correlation_id
        )

        logger.info(
            "Job created successfully",
            correlation_id=correlation_id,
            job_id=str(job.id),
            category_id=str(job_request.category_id),
            celery_task_id=task_result.id
        )

        # Refresh job data
        updated_job = await job_repo.get_by_id(job.id)

        # Create response with raw data (bypass Pydantic validation issues)
        from fastapi.responses import JSONResponse

        response_data = {
            "id": str(updated_job.id),
            "category_id": str(updated_job.category_id),
            "category_name": category.name,
            "status": str(updated_job.status) if hasattr(updated_job.status, 'value') else updated_job.status,
            "celery_task_id": updated_job.celery_task_id,
            "started_at": updated_job.started_at.isoformat() if updated_job.started_at else None,
            "completed_at": updated_job.completed_at.isoformat() if updated_job.completed_at else None,
            "articles_found": updated_job.articles_found,
            "articles_saved": updated_job.articles_saved,
            "error_message": updated_job.error_message,
            "retry_count": updated_job.retry_count,
            "priority": updated_job.priority,
            "correlation_id": updated_job.correlation_id,
            "created_at": updated_job.created_at.isoformat() if updated_job.created_at else None,
            "updated_at": updated_job.updated_at.isoformat() if updated_job.updated_at else None,
            "duration_seconds": updated_job.duration_seconds,
            "success_rate": updated_job.success_rate
        }
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create job",
            correlation_id=correlation_id,
            category_id=str(job_request.category_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(e)}"
        )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by job status"),
    category_id: Optional[UUID] = Query(None, description="Filter by category ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    job_repo: CrawlJobRepository = Depends(get_job_repository)
) -> JobListResponse:
    """List crawl jobs with optional filtering.

    This endpoint returns a list of jobs with optional status and category filtering.
    Results are paginated and include summary statistics.

    Args:
        request: FastAPI request object for correlation ID
        status: Optional status filter (pending, running, completed, failed)
        category_id: Optional category UUID filter
        limit: Maximum number of jobs to return (1-100)
        job_repo: Job repository dependency

    Returns:
        List of jobs with summary statistics

    Raises:
        HTTPException: If filtering or retrieval fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Listing jobs",
        correlation_id=correlation_id,
        status_filter=status,
        category_id=str(category_id) if category_id else None,
        limit=limit
    )

    try:
        # Validate status filter if provided
        status_enum = None
        if status:
            try:
                status_enum = CrawlJobStatus(status.lower())
            except ValueError:
                valid_statuses = [s.value for s in CrawlJobStatus]
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{status}'. Valid options: {valid_statuses}"
                )

        # Get jobs based on filters
        if category_id and status_enum:
            jobs = await job_repo.get_jobs_by_category(
                category_id=category_id,
                status=status_enum,
                limit=limit
            )
        elif category_id:
            jobs = await job_repo.get_jobs_by_category(
                category_id=category_id,
                limit=limit
            )
        elif status_enum == CrawlJobStatus.PENDING:
            jobs = await job_repo.get_pending_jobs(limit=limit)
        elif status_enum == CrawlJobStatus.RUNNING:
            jobs = await job_repo.get_running_jobs(limit=limit)
        elif status_enum == CrawlJobStatus.COMPLETED:
            jobs = await job_repo.get_completed_jobs(limit=limit)
        elif status_enum == CrawlJobStatus.FAILED:
            jobs = await job_repo.get_failed_jobs(limit=limit)
        else:
            # Get all active jobs by default
            jobs = await job_repo.get_active_jobs(limit=limit)

        # Get status counts for summary
        all_jobs = await job_repo.get_active_jobs(limit=1000)  # Get more for accurate counts
        status_counts = {}
        for status_value in CrawlJobStatus:
            status_counts[status_value.value] = sum(1 for job in all_jobs if job.status == status_value)

        # Get category names for job responses
        category_ids = list(set(job.category_id for job in jobs))
        category_lookup = {}

        # Create new category repository instance for category lookup
        from src.database.repositories.category_repo import CategoryRepository
        lookup_category_repo = CategoryRepository()

        for category_id in category_ids:
            try:
                category = await lookup_category_repo.get_by_id(category_id)
                if category:
                    category_lookup[str(category_id)] = category.name
                else:
                    category_lookup[str(category_id)] = "Unknown Category"
            except Exception as e:
                logger.warning(f"Failed to get category name for {category_id}: {e}")
                category_lookup[str(category_id)] = "Unknown Category"

        # Convert to response format
        job_responses = [
            JobResponse(
                id=job.id,
                category_id=job.category_id,
                category_name=category_lookup.get(str(job.category_id), "Unknown Category"),
                status=CrawlJobStatus(job.status) if isinstance(job.status, str) else job.status,
                celery_task_id=job.celery_task_id,
                started_at=job.started_at,
                completed_at=job.completed_at,
                articles_found=job.articles_found,
                articles_saved=job.articles_saved,
                error_message=job.error_message,
                retry_count=job.retry_count,
                priority=job.priority,
                correlation_id=job.correlation_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
                duration_seconds=job.duration_seconds,
                success_rate=job.success_rate
            )
            for job in jobs
        ]

        logger.info(
            "Jobs retrieved successfully",
            correlation_id=correlation_id,
            total_returned=len(job_responses),
            status_filter=status,
            category_id=str(category_id) if category_id else None
        )

        return JobListResponse(
            jobs=job_responses,
            total=len(job_responses),
            pending_count=status_counts.get('pending', 0),
            running_count=status_counts.get('running', 0),
            completed_count=status_counts.get('completed', 0),
            failed_count=status_counts.get('failed', 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to list jobs",
            correlation_id=correlation_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    request: Request,
    job_repo: CrawlJobRepository = Depends(get_job_repository)
) -> JobStatusResponse:
    """Get detailed status information for a specific job.

    This endpoint returns the current status and progress information
    for a specific job, including execution details and error information.

    Args:
        job_id: UUID of the job to check
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency

    Returns:
        Job status and progress information

    Raises:
        HTTPException: If job not found or status retrieval fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Getting job status",
        correlation_id=correlation_id,
        job_id=str(job_id)
    )

    try:
        # Get job by ID
        job = await job_repo.get_by_id(job_id)
        if not job:
            logger.warning(
                "Job not found",
                correlation_id=correlation_id,
                job_id=str(job_id)
            )
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID {job_id} not found"
            )

        # Build progress information
        progress = None
        if job.status == CrawlJobStatus.RUNNING:
            progress = {
                "articles_found": job.articles_found,
                "articles_saved": job.articles_saved,
                "success_rate": job.success_rate
            }

            # Estimate completion time if we have start time
            if job.started_at:
                elapsed_minutes = (datetime.now(timezone.utc) - job.started_at).total_seconds() / 60
                if elapsed_minutes > 5:  # Only estimate after 5 minutes
                    # Simple estimation based on current rate
                    if job.articles_found > 0:
                        estimated_total = max(job.articles_found * 1.5, 50)  # Rough estimate
                        progress["estimated_total"] = int(estimated_total)

        logger.info(
            "Job status retrieved",
            correlation_id=correlation_id,
            job_id=str(job_id),
            status=job.status.value
        )

        return JobStatusResponse(
            id=job.id,
            status=CrawlJobStatus(job.status) if isinstance(job.status, str) else job.status,
            progress=progress,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get job status",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job status: {str(e)}"
        )


@router.patch("/jobs/{job_id}/priority", response_model=JobResponse)
async def update_job_priority(
    job_id: UUID,
    priority_update: PriorityUpdateRequest,
    request: Request,
    job_repo: CrawlJobRepository = Depends(get_job_repository)
) -> JobResponse:
    """Update job priority for Run Now functionality.

    This endpoint updates the priority of a pending crawl job to enable
    immediate execution. High priority jobs (>= 5) will be processed as
    soon as worker resources become available.

    Args:
        job_id: UUID of the job to update
        priority_update: Priority update request data
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency

    Returns:
        Updated job data with new priority

    Raises:
        HTTPException: If job not found, running, or update fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Updating job priority",
        correlation_id=correlation_id,
        job_id=str(job_id),
        new_priority=priority_update.priority
    )

    try:
        # Update job priority
        updated_job = await job_repo.update_job_priority(
            job_id=job_id,
            priority=priority_update.priority,
            correlation_id=correlation_id
        )

        # Get category name for response
        category_repo = CategoryRepository()
        category = await category_repo.get_by_id(updated_job.category_id)
        category_name = category.name if category else "Unknown Category"

        # TODO: Trigger Celery priority update for pending jobs
        # if updated_job.status == CrawlJobStatus.PENDING:
        #     await update_job_priority_task.delay(job_id, priority_update.priority)

        logger.info(
            "Job priority updated successfully",
            correlation_id=correlation_id,
            job_id=str(job_id),
            new_priority=priority_update.priority
        )

        return JobResponse(
            id=updated_job.id,
            category_id=updated_job.category_id,
            category_name=category_name,
            status=updated_job.status,
            celery_task_id=updated_job.celery_task_id,
            started_at=updated_job.started_at,
            completed_at=updated_job.completed_at,
            articles_found=updated_job.articles_found,
            articles_saved=updated_job.articles_saved,
            error_message=updated_job.error_message,
            retry_count=updated_job.retry_count,
            priority=updated_job.priority,
            correlation_id=updated_job.correlation_id,
            created_at=updated_job.created_at,
            updated_at=updated_job.updated_at,
            duration_seconds=updated_job.duration_seconds,
            success_rate=updated_job.success_rate
        )

    except ValueError as e:
        logger.warning(
            "Job priority update failed",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=404 if "not found" in str(e) else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to update job priority",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update job priority: {str(e)}"
        )


@router.put("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    job_update: JobUpdateRequest,
    request: Request,
    job_repo: CrawlJobRepository = Depends(get_job_repository)
) -> JobResponse:
    """Update job configuration.

    This endpoint allows updating job settings like priority, retry count,
    and metadata. Running jobs cannot be updated.

    Args:
        job_id: UUID of the job to update
        job_update: Job update request data
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency

    Returns:
        Updated job data

    Raises:
        HTTPException: If job not found, running, or update fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Updating job configuration",
        correlation_id=correlation_id,
        job_id=str(job_id)
    )

    try:
        # Prepare updates dictionary
        updates = {}
        if job_update.priority is not None:
            updates['priority'] = job_update.priority
        if job_update.retry_count is not None:
            updates['retry_count'] = job_update.retry_count
        if job_update.job_metadata is not None:
            updates['job_metadata'] = job_update.job_metadata

        if not updates:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )

        # Update job
        updated_job = await job_repo.update_job(
            job_id=job_id,
            updates=updates,
            correlation_id=correlation_id
        )

        # Get category name for response
        category_repo = CategoryRepository()
        category = await category_repo.get_by_id(updated_job.category_id)
        category_name = category.name if category else "Unknown Category"

        logger.info(
            "Job configuration updated successfully",
            correlation_id=correlation_id,
            job_id=str(job_id),
            updates=list(updates.keys())
        )

        return JobResponse(
            id=updated_job.id,
            category_id=updated_job.category_id,
            category_name=category_name,
            status=updated_job.status,
            celery_task_id=updated_job.celery_task_id,
            started_at=updated_job.started_at,
            completed_at=updated_job.completed_at,
            articles_found=updated_job.articles_found,
            articles_saved=updated_job.articles_saved,
            error_message=updated_job.error_message,
            retry_count=updated_job.retry_count,
            priority=updated_job.priority,
            correlation_id=updated_job.correlation_id,
            created_at=updated_job.created_at,
            updated_at=updated_job.updated_at,
            duration_seconds=updated_job.duration_seconds,
            success_rate=updated_job.success_rate
        )

    except ValueError as e:
        logger.warning(
            "Job update failed",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=404 if "not found" in str(e) else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to update job",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update job: {str(e)}"
        )


@router.delete("/jobs/{job_id}", response_model=JobDeletionResponse)
async def delete_job(
    job_id: UUID,
    request: Request,
    deletion_request: JobDeletionRequest = JobDeletionRequest(),
    job_repo: CrawlJobRepository = Depends(get_job_repository)
) -> JobDeletionResponse:
    """Delete job with impact analysis.

    This endpoint deletes a crawl job and provides impact analysis showing
    affected articles. Can optionally force deletion of running jobs.

    Args:
        job_id: UUID of the job to delete
        deletion_request: Deletion configuration
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency

    Returns:
        Deletion confirmation with impact analysis

    Raises:
        HTTPException: If job not found or deletion fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Deleting job",
        correlation_id=correlation_id,
        job_id=str(job_id),
        force=deletion_request.force,
        delete_articles=deletion_request.delete_articles
    )

    try:
        # Delete job with impact analysis
        impact = await job_repo.delete_job(
            job_id=job_id,
            force=deletion_request.force,
            delete_articles=deletion_request.delete_articles,
            correlation_id=correlation_id
        )

        deletion_time = datetime.now(timezone.utc)

        logger.info(
            "Job deleted successfully",
            correlation_id=correlation_id,
            job_id=str(job_id),
            impact=impact
        )

        return JobDeletionResponse(
            job_id=job_id,
            impact=impact,
            message="Job deleted successfully",
            deleted_at=deletion_time
        )

    except ValueError as e:
        logger.warning(
            "Job deletion failed",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=404 if "not found" in str(e) else 400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to delete job",
            correlation_id=correlation_id,
            job_id=str(job_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete job: {str(e)}"
        )

@router.post("/jobs/{job_id}/execute", response_model=JobResponse)
async def execute_job_immediately(
    job_id: UUID,
    request: Request,
    job_repo: CrawlJobRepository = Depends(get_job_repository),
    category_repo: CategoryRepository = Depends(get_category_repository)
) -> JobResponse:
    """Execute existing job immediately (Run Now functionality).

    This endpoint creates a new high-priority job based on an existing job
    configuration and triggers immediate execution. This is the critical
    fix for the "Run Now" button functionality.

    Args:
        job_id: UUID of the job to execute immediately
        request: FastAPI request object for correlation ID
        job_repo: Job repository dependency
        category_repo: Category repository dependency

    Returns:
        New job data with high priority and immediate execution

    Raises:
        HTTPException: If job not found or execution fails
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.info(
        "Executing job immediately (Run Now)",
        correlation_id=correlation_id,
        source_job_id=str(job_id)
    )

    try:
        # Get the source job
        source_job = await job_repo.get_by_id(job_id)
        if not source_job:
            logger.warning(
                "Source job not found for immediate execution",
                correlation_id=correlation_id,
                job_id=str(job_id)
            )
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID {job_id} not found"
            )

        # Verify category exists and is active
        category = await category_repo.get_by_id(source_job.category_id)
        if not category:
            logger.warning(
                "Category not found for immediate execution",
                correlation_id=correlation_id,
                category_id=str(source_job.category_id)
            )
            raise HTTPException(
                status_code=404,
                detail=f"Category with ID {source_job.category_id} not found"
            )

        if not category.is_active:
            logger.warning(
                "Attempted immediate execution for inactive category",
                correlation_id=correlation_id,
                category_id=str(source_job.category_id)
            )
            raise HTTPException(
                status_code=400,
                detail=f"Category '{category.name}' is not active"
            )

        # Create new job with high priority for immediate execution
        new_job = await job_repo.create_job(
            category_id=source_job.category_id,
            priority=10,  # Maximum priority for immediate execution
            correlation_id=correlation_id,
            metadata={"source_job_id": str(job_id), "execution_type": "immediate"}
        )

        # Trigger background task with high priority
        task_result = trigger_category_crawl_task.delay(
            category_id=str(source_job.category_id),
            priority=10,
            metadata={"source_job_id": str(job_id), "execution_type": "immediate"}
        )

        # Update job with Celery task ID
        await job_repo.update_status(
            job_id=new_job.id,
            status=CrawlJobStatus.PENDING,
            celery_task_id=task_result.id,
            correlation_id=correlation_id
        )

        logger.info(
            "Job scheduled for immediate execution",
            correlation_id=correlation_id,
            source_job_id=str(job_id),
            new_job_id=str(new_job.id),
            category_id=str(source_job.category_id),
            celery_task_id=task_result.id
        )

        # Refresh job data
        updated_job = await job_repo.get_by_id(new_job.id)

        # Create response with raw data (bypass Pydantic validation issues)
        response_data = {
            "id": str(updated_job.id),
            "category_id": str(updated_job.category_id),
            "category_name": category.name,
            "status": str(updated_job.status) if hasattr(updated_job.status, 'value') else updated_job.status,
            "celery_task_id": updated_job.celery_task_id,
            "started_at": updated_job.started_at.isoformat() if updated_job.started_at else None,
            "completed_at": updated_job.completed_at.isoformat() if updated_job.completed_at else None,
            "articles_found": updated_job.articles_found,
            "articles_saved": updated_job.articles_saved,
            "error_message": updated_job.error_message,
            "retry_count": updated_job.retry_count,
            "priority": updated_job.priority,
            "correlation_id": updated_job.correlation_id,
            "created_at": updated_job.created_at.isoformat() if updated_job.created_at else None,
            "updated_at": updated_job.updated_at.isoformat() if updated_job.updated_at else None,
            "duration_seconds": updated_job.duration_seconds,
            "success_rate": updated_job.success_rate
        }
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to execute job immediately",
            correlation_id=correlation_id,
            source_job_id=str(job_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute job immediately: {str(e)}"
        )