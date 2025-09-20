# Coding Standards

## Overview

This document defines the coding standards for the Google News Scraper job-centric enhancement. These standards ensure consistency, maintainability, and quality across the fullstack codebase while supporting AI-driven development workflows.

## Critical Fullstack Rules

These rules prevent common mistakes and ensure system integrity:

- **Type Sharing:** Always define types in shared/ directory and import from there - never duplicate interfaces between frontend and backend
- **API Calls:** Never make direct HTTP calls in components - use the service layer with proper error handling and correlation ID tracking
- **Environment Variables:** Access only through config objects, never process.env directly in components or business logic
- **Error Handling:** All API routes must use the standard error handler with correlation ID tracking and structured logging
- **State Updates:** Never mutate state directly - use proper state management patterns with React Context and immutable updates
- **Database Queries:** Always use repository pattern, never raw SQL in route handlers or business logic
- **Job Priority Updates:** Use atomic database operations for job priority changes to prevent race conditions
- **Article Export:** All exports must support UTF-8 encoding for Vietnamese characters with proper MIME types
- **Real-time Updates:** Use WebSocket connections sparingly, prefer polling for job status updates to avoid connection overhead
- **Container Health:** All containers must implement proper health checks and graceful shutdown handling
- **Correlation Tracking:** Every request must include correlation ID for distributed tracing across services
- **Authentication:** Always validate JWT tokens and user permissions before accessing protected resources

## Naming Conventions

### Comprehensive Naming Standards

| Element | Frontend | Backend | Example | Notes |
|---------|----------|---------|---------|-------|
| **Components** | PascalCase | - | `JobArticlesModal.tsx` | React components |
| **Hooks** | camelCase with 'use' | - | `useJobArticles.ts` | Custom React hooks |
| **API Routes** | - | kebab-case | `/api/v1/job-articles` | REST endpoint paths |
| **Database Tables** | - | snake_case | `crawl_jobs` | PostgreSQL tables |
| **Database Columns** | - | snake_case | `articles_found` | Column names |
| **Environment Variables** | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `CELERY_BROKER_URL` | Both environments |
| **Service Methods** | camelCase | snake_case | `getJobArticles` / `get_job_articles` | Language conventions |
| **Event Handlers** | camelCase with 'handle' | - | `handleRunNowClick` | UI event handlers |
| **Constants** | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` | Application constants |
| **Type Interfaces** | PascalCase | PascalCase | `CrawlJob` | TypeScript interfaces |
| **Enum Values** | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `CRAWL_JOB_STATUS.PENDING` | Enum constants |
| **File Names** | kebab-case | snake_case | `job-service.ts` / `job_repo.py` | File naming |
| **CSS Classes** | kebab-case | - | `job-actions-container` | CSS/Tailwind classes |
| **Test Files** | component.test.ts | test_component.py | `job-list.test.tsx` / `test_job_repo.py` | Test file naming |

### Special Naming Rules

#### Frontend Specific
- **Page Components:** End with `Page` (e.g., `JobsPage.tsx`)
- **Modal Components:** End with `Modal` (e.g., `JobEditModal.tsx`)
- **Context Providers:** End with `Provider` (e.g., `JobsProvider.tsx`)
- **Custom Hooks:** Start with `use` (e.g., `useJobActions.ts`)
- **Service Classes:** End with `Service` (e.g., `JobsService.ts`)

#### Backend Specific
- **Repository Classes:** End with `Repository` (e.g., `CrawlJobRepository`)
- **Schema Classes:** End with schema type (e.g., `JobResponse`, `JobCreateRequest`)
- **Exception Classes:** End with `Exception` (e.g., `JobNotFoundException`)
- **Task Functions:** End with `_task` (e.g., `crawl_category_task`)
- **Migration Files:** Include version and description (e.g., `001_create_crawl_jobs.py`)

## Code Structure Standards

### Frontend Code Organization

```typescript
// File: components/jobs/JobActionButtons.tsx
import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';

// 1. External library imports
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// 2. Internal type imports
import { CrawlJob, CrawlJobStatus } from '@/types/job';

// 3. Hook and service imports
import { useJobs } from '@/hooks/useJobs';
import { useNotifications } from '@/hooks/useNotifications';

// 4. Interface definition
interface JobActionButtonsProps {
  job: CrawlJob;
  onJobUpdate?: (job: CrawlJob) => void;
  className?: string;
}

// 5. Component implementation
export const JobActionButtons: React.FC<JobActionButtonsProps> = ({
  job,
  onJobUpdate,
  className
}) => {
  // 6. State declarations
  const [isUpdating, setIsUpdating] = useState(false);

  // 7. Hook usage
  const { updateJobPriority } = useJobs();
  const { showSuccess, showError } = useNotifications();

  // 8. Event handlers (useCallback for performance)
  const handleRunNow = useCallback(async () => {
    // Implementation
  }, [job, updateJobPriority, showSuccess, showError, onJobUpdate]);

  // 9. Computed values
  const canRunNow = job.status === CrawlJobStatus.PENDING;

  // 10. Render
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Component JSX */}
    </div>
  );
};

// 11. Default export
export default JobActionButtons;
```

### Backend Code Organization

```python
# File: src/api/routes/jobs.py
"""
Job management API routes for Google News Scraper.

This module provides job-centric functionality including:
- Job listing with filtering and pagination
- Priority-based job queue management
- Job status tracking and updates
"""

# 1. Standard library imports
from typing import Optional, List, Dict, Any
from datetime import datetime

# 2. Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

# 3. Internal imports - database
from src.database.connection import get_database_session
from src.database.repositories.job_repo import CrawlJobRepository

# 4. Internal imports - schemas
from src.api.schemas.job import (
    JobResponse, JobCreateRequest, JobUpdateRequest, PriorityUpdateRequest
)
from src.api.schemas.common import PaginatedResponse

# 5. Internal imports - dependencies and auth
from src.api.dependencies.pagination import PaginationParams
from src.api.dependencies.auth import get_current_user

# 6. Internal imports - business logic
from src.core.scheduler.tasks import update_job_priority_task

# 7. Internal imports - exceptions
from src.shared.exceptions import (
    JobNotFoundException, JobAlreadyRunningException
)

# 8. Logger setup
logger = structlog.get_logger(__name__)

# 9. Router initialization
router = APIRouter(prefix="/jobs", tags=["jobs"])

# 10. Route handlers
@router.get("/", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    # Parameters with proper typing and documentation
    status: Optional[str] = Query(None, description="Filter by job status"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    List crawl jobs with filtering and pagination.

    Supports job-centric workflow with priority-based sorting
    and comprehensive filtering options.
    """
    # Implementation with proper error handling and logging
    pass
```

## Error Handling Standards

### Frontend Error Handling

```typescript
// Standardized error handling patterns

// 1. API Error Interface
interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  requestId: string;
}

// 2. Error Handler Service
class ErrorHandler {
  static handle(error: any, context?: string): void {
    const correlationId = error.response?.headers?.['x-correlation-id'];

    // Log error with context
    console.error(`[${context || 'Unknown'}] API Error:`, {
      code: error.response?.data?.error?.code,
      message: error.response?.data?.error?.message,
      correlationId,
      url: error.config?.url,
      method: error.config?.method
    });

    // Show user-friendly message
    toast.error(this.getUserMessage(error));
  }

  private static getUserMessage(error: any): string {
    const errorCode = error.response?.data?.error?.code;

    switch (errorCode) {
      case 'JOB_NOT_FOUND':
        return 'Job not found. It may have been deleted.';
      case 'JOB_ALREADY_RUNNING':
        return 'Cannot modify job that is currently running.';
      case 'PRIORITY_UPDATE_FAILED':
        return 'Failed to update job priority. Please try again.';
      default:
        return 'An unexpected error occurred. Please try again.';
    }
  }
}

// 3. Hook-level error handling
export const useJobActions = () => {
  const updateJobPriority = async (jobId: string, priority: number) => {
    try {
      const result = await JobsService.updateJobPriority(jobId, priority);
      toast.success('Job priority updated successfully');
      return result;
    } catch (error) {
      ErrorHandler.handle(error, 'updateJobPriority');
      throw error; // Re-throw for component-level handling
    }
  };

  return { updateJobPriority };
};
```

### Backend Error Handling

```python
# Standardized exception hierarchy and handling

# 1. Custom Exception Base Classes
class AppException(Exception):
    """Base application exception with structured error information."""

    def __init__(
        self,
        message: str,
        code: str,
        details: Dict[str, Any] = None,
        status_code: int = 400
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(AppException):
    """Validation-related errors."""

    def __init__(self, message: str, field: str = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {},
            status_code=422
        )

# 2. Domain-specific exceptions
class JobNotFoundException(AppException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job with ID {job_id} not found",
            code="JOB_NOT_FOUND",
            details={"job_id": job_id},
            status_code=404
        )

# 3. Exception handlers
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.warning(
        "Application exception",
        correlation_id=correlation_id,
        error_code=exc.code,
        error_message=exc.message,
        error_details=exc.details,
        path=request.url.path
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.utcnow().isoformat(),
                "requestId": correlation_id
            }
        },
        headers={"X-Correlation-ID": correlation_id}
    )

# 4. Route-level error handling
@router.patch("/{job_id}/priority")
async def update_job_priority(
    job_id: str,
    priority_update: PriorityUpdateRequest,
    db: AsyncSession = Depends(get_database_session)
):
    """Update job priority with comprehensive error handling."""

    # Validate input
    if not (0 <= priority_update.priority <= 10):
        raise ValidationError(
            message="Priority must be between 0 and 10",
            field="priority"
        )

    # Check job exists
    job_repo = CrawlJobRepository(db)
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise JobNotFoundException(job_id)

    # Business logic validation
    if job.status == "running":
        raise AppException(
            message="Cannot modify running job",
            code="JOB_ALREADY_RUNNING",
            details={"job_id": job_id, "current_status": job.status}
        )

    try:
        # Perform update
        updated_job = await job_repo.update_job_priority(job_id, priority_update.priority)
        return JobResponse.from_orm(updated_job)

    except Exception as e:
        logger.error(
            "Failed to update job priority",
            job_id=job_id,
            priority=priority_update.priority,
            error=str(e)
        )
        raise AppException(
            message="Failed to update job priority",
            code="PRIORITY_UPDATE_FAILED",
            details={"job_id": job_id}
        )
```

## Testing Standards

### Frontend Testing Patterns

```typescript
// Test file: components/jobs/JobActionButtons.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { JobActionButtons } from './JobActionButtons';
import { JobsService } from '@/services/JobsService';
import { CrawlJobStatus } from '@/types/job';

// 1. Mock external dependencies
vi.mock('@/services/JobsService');
vi.mock('@/hooks/useNotifications');

// 2. Test data setup
const mockJob = {
  id: 'job-123',
  status: CrawlJobStatus.PENDING,
  priority: 0,
  category_id: 'cat-456',
  articles_found: 0,
  articles_saved: 0,
  created_at: '2025-09-15T10:00:00Z'
};

// 3. Test suite organization
describe('JobActionButtons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Run Now functionality', () => {
    it('should update job priority when Run Now is clicked', async () => {
      // Arrange
      const mockUpdatePriority = vi.mocked(JobsService.updateJobPriority)
        .mockResolvedValue({ ...mockJob, priority: 10 });

      const onJobUpdate = vi.fn();

      // Act
      render(
        <JobActionButtons
          job={mockJob}
          onJobUpdate={onJobUpdate}
        />
      );

      fireEvent.click(screen.getByText('🚀 Run Now'));

      // Assert
      await waitFor(() => {
        expect(mockUpdatePriority).toHaveBeenCalledWith('job-123', 10);
        expect(onJobUpdate).toHaveBeenCalledWith({ ...mockJob, priority: 10 });
      });
    });

    it('should not show Run Now for running jobs', () => {
      render(
        <JobActionButtons
          job={{ ...mockJob, status: CrawlJobStatus.RUNNING }}
        />
      );

      expect(screen.queryByText('🚀 Run Now')).not.toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('should handle priority update errors gracefully', async () => {
      // Mock error
      vi.mocked(JobsService.updateJobPriority)
        .mockRejectedValue(new Error('Network error'));

      render(<JobActionButtons job={mockJob} />);

      fireEvent.click(screen.getByText('🚀 Run Now'));

      // Should show error message (would need to mock notification hook)
      await waitFor(() => {
        expect(screen.getByText('🚀 Run Now')).not.toBeDisabled();
      });
    });
  });
});
```

### Backend Testing Patterns

```python
# Test file: tests/api/test_jobs.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import Mock, patch

from src.api.main import app
from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from tests.conftest import override_get_db

client = TestClient(app)

class TestJobRoutes:
    """Test suite for job management routes."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for tests."""
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def sample_job(self, db_session: AsyncSession):
        """Create a sample job for testing."""
        job = CrawlJob(
            id="job-123",
            category_id="cat-456",
            status=CrawlJobStatus.PENDING,
            priority=0,
            articles_found=0,
            articles_saved=0
        )
        db_session.add(job)
        db_session.commit()
        return job

    def test_update_job_priority_success(self, sample_job, auth_headers):
        """Test successful job priority update."""
        # Act
        response = client.patch(
            f"/api/v1/jobs/{sample_job.id}/priority",
            json={"priority": 10},
            headers=auth_headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == 10
        assert data["id"] == str(sample_job.id)

    def test_update_job_priority_not_found(self, auth_headers):
        """Test priority update for non-existent job."""
        response = client.patch(
            "/api/v1/jobs/non-existent/priority",
            json={"priority": 10},
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "JOB_NOT_FOUND"

    def test_update_job_priority_validation_error(self, sample_job, auth_headers):
        """Test priority update with invalid priority value."""
        response = client.patch(
            f"/api/v1/jobs/{sample_job.id}/priority",
            json={"priority": 15},  # Invalid: > 10
            headers=auth_headers
        )

        assert response.status_code == 422
        assert "priority" in response.json()["error"]["details"]["field"]

    @patch('src.core.scheduler.tasks.update_job_priority_task.delay')
    def test_priority_update_triggers_celery_task(
        self,
        mock_celery_task,
        sample_job,
        auth_headers
    ):
        """Test that high priority updates trigger Celery task."""
        response = client.patch(
            f"/api/v1/jobs/{sample_job.id}/priority",
            json={"priority": 8},
            headers=auth_headers
        )

        assert response.status_code == 200
        mock_celery_task.assert_called_once_with(str(sample_job.id), 8)

    def test_list_jobs_pagination(self, auth_headers):
        """Test job listing with pagination."""
        response = client.get(
            "/api/v1/jobs",
            params={"page": 1, "size": 10},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data

    def test_list_jobs_filtering(self, sample_job, auth_headers):
        """Test job listing with status filtering."""
        response = client.get(
            "/api/v1/jobs",
            params={"status": "pending"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert all(job["status"] == "pending" for job in data["items"])
```

## Documentation Standards

### Code Documentation

```typescript
/**
 * Custom hook for managing job-related operations with optimistic updates.
 *
 * Provides methods for job CRUD operations with built-in error handling,
 * loading states, and real-time updates for job-centric workflows.
 *
 * @example
 * ```tsx
 * const { jobs, updateJobPriority, loading, error } = useJobs();
 *
 * const handleRunNow = async (jobId: string) => {
 *   try {
 *     await updateJobPriority(jobId, 10);
 *     toast.success('Job prioritized successfully');
 *   } catch (error) {
 *     // Error handling is automatic via ErrorHandler
 *   }
 * };
 * ```
 *
 * @returns Object containing job state and action methods
 */
export const useJobs = (): UseJobsReturn => {
  // Implementation
};

/**
 * Updates job priority with optimistic UI updates and rollback on failure.
 *
 * @param jobId - Unique identifier for the job
 * @param priority - New priority value (0-10, higher = more urgent)
 * @returns Promise resolving to updated job data
 * @throws {JobNotFoundException} When job doesn't exist
 * @throws {JobAlreadyRunningException} When job is currently running
 */
const updateJobPriority = async (
  jobId: string,
  priority: number
): Promise<CrawlJob> => {
  // Implementation
};
```

```python
def update_job_priority(
    self,
    job_id: str,
    priority: int
) -> CrawlJob:
    """
    Update job priority with atomic operation and optimistic locking.

    This method ensures thread-safe priority updates for the job queue
    system, preventing race conditions during concurrent updates.

    Args:
        job_id: Unique identifier for the job to update
        priority: New priority value (0-10, higher = more urgent)

    Returns:
        Updated CrawlJob instance with new priority

    Raises:
        ValueError: If job_id not found or update fails
        IntegrityError: If concurrent update detected

    Example:
        >>> job_repo = CrawlJobRepository(db)
        >>> updated_job = await job_repo.update_job_priority("job-123", 10)
        >>> assert updated_job.priority == 10
    """
    # Implementation
```

### API Documentation Standards

```python
@router.patch("/{job_id}/priority", response_model=JobResponse)
async def update_job_priority(
    job_id: str = Path(..., description="Unique job identifier"),
    priority_update: PriorityUpdateRequest = Body(...),
    background_tasks: BackgroundTasks = Depends(),
    db: AsyncSession = Depends(get_database_session),
    current_user = Depends(get_current_user)
):
    """
    Update job priority for Run Now functionality.

    Updates the priority of a pending crawl job to enable immediate execution.
    High priority jobs (>= 5) will be processed as soon as worker resources
    become available, bypassing the normal queue order.

    **Priority Levels:**
    - 0-4: Normal priority (queue order based on creation time)
    - 5-7: High priority (processed before normal jobs)
    - 8-10: Critical priority (immediate processing)

    **Business Rules:**
    - Only pending jobs can have their priority updated
    - Running jobs cannot be re-prioritized
    - Completed/failed jobs cannot be re-prioritized
    - Priority changes trigger Celery task queue reordering

    **Rate Limiting:** 100 requests/hour per user

    **Audit Trail:** All priority changes are logged with user ID and timestamp
    """
    # Implementation
```

This comprehensive coding standards document ensures consistency and quality across the entire Google News Scraper codebase while supporting efficient AI-driven development workflows.