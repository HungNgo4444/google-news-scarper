"""Tests for Celery task execution and job management.

This module tests the Celery tasks that handle job scheduling, execution, and maintenance.
Tests include mock scenarios for various success and failure conditions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

from src.core.scheduler.tasks import (
    crawl_category_task,
    cleanup_old_jobs_task,
    monitor_job_health_task,
    trigger_category_crawl_task
)
from src.database.models.crawl_job import CrawlJobStatus
from src.shared.exceptions import CrawlerError, RateLimitExceededError


@pytest.fixture
def mock_category():
    """Mock category object for testing."""
    category = MagicMock()
    category.id = uuid4()
    category.name = "Technology"
    category.keywords = ["python", "javascript"]
    category.exclude_keywords = ["jobs"]
    category.is_active = True
    return category


@pytest.fixture
def mock_job():
    """Mock crawl job object for testing."""
    job = MagicMock()
    job.id = uuid4()
    job.status = CrawlJobStatus.PENDING
    job.created_at = datetime.now(timezone.utc)
    job.started_at = None
    job.completed_at = None
    return job


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    settings = MagicMock()
    settings.JOB_EXECUTION_TIMEOUT = 1800
    settings.JOB_CLEANUP_DAYS = 30
    settings.CELERY_BROKER_URL = "redis://localhost:6379/0"
    return settings


class TestCrawlCategoryTask:
    """Test cases for crawl_category_task."""
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.CategoryRepository')
    @patch('src.core.scheduler.tasks.ArticleRepository')
    @patch('src.core.scheduler.tasks.ArticleExtractor')
    @patch('src.core.scheduler.tasks.CrawlerEngine')
    def test_successful_crawl(
        self, 
        mock_crawler_engine,
        mock_article_extractor,
        mock_article_repo,
        mock_category_repo,
        mock_job_repo,
        mock_get_settings,
        mock_category,
        mock_job,
        mock_settings
    ):
        """Test successful category crawl execution."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.update_status = AsyncMock(return_value=True)
        
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=mock_category)
        
        # Mock crawler execution
        crawler_instance = AsyncMock()
        mock_crawler_engine.return_value = crawler_instance
        
        # Mock the async crawl execution function
        with patch('src.core.scheduler.tasks._execute_crawl_with_tracking') as mock_crawl:
            mock_crawl.return_value = (10, 8)  # 10 found, 8 saved
            
            # Create mock task instance
            mock_task = MagicMock()
            mock_task.request.id = "test-task-id"
            mock_task.request.retries = 0
            
            # Execute task
            result = asyncio.run(
                crawl_category_task(
                    mock_task,
                    str(mock_category.id),
                    str(mock_job.id)
                )
            )
        
        # Verify results
        assert result["status"] == "completed"
        assert result["articles_found"] == 10
        assert result["articles_saved"] == 8
        assert "correlation_id" in result
        
        # Verify repository calls
        job_repo_instance.update_status.assert_any_call(
            job_id=mock_job.id,
            status="running",
            started_at=pytest.any,
            celery_task_id="test-task-id",
            correlation_id=pytest.any
        )
        
        job_repo_instance.update_status.assert_any_call(
            job_id=mock_job.id,
            status="completed",
            articles_found=10,
            articles_saved=8,
            completed_at=pytest.any
        )
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.CategoryRepository')
    def test_category_not_found(
        self,
        mock_category_repo,
        mock_job_repo,
        mock_get_settings,
        mock_job,
        mock_settings
    ):
        """Test handling when category is not found."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.update_status = AsyncMock(return_value=True)
        
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=None)  # Category not found
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "test-task-id"
        mock_task.request.retries = 0
        
        # Execute task
        result = asyncio.run(
            crawl_category_task(
                mock_task,
                str(uuid4()),
                str(mock_job.id)
            )
        )
        
        # Verify results
        assert result["status"] == "failed"
        assert "not found" in result["error"]
        
        # Verify job status was updated to failed
        job_repo_instance.update_status.assert_any_call(
            job_id=mock_job.id,
            status="failed",
            error_message=pytest.any,
            completed_at=pytest.any
        )
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.CategoryRepository')
    def test_inactive_category(
        self,
        mock_category_repo,
        mock_job_repo,
        mock_get_settings,
        mock_category,
        mock_job,
        mock_settings
    ):
        """Test handling of inactive categories."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        mock_category.is_active = False  # Make category inactive
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.update_status = AsyncMock(return_value=True)
        
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=mock_category)
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "test-task-id"
        mock_task.request.retries = 0
        
        # Execute task
        result = asyncio.run(
            crawl_category_task(
                mock_task,
                str(mock_category.id),
                str(mock_job.id)
            )
        )
        
        # Verify results
        assert result["status"] == "skipped"
        assert "not active" in result["reason"]
        
        # Verify job status was updated to completed (not failed, as it's not an error)
        job_repo_instance.update_status.assert_called_with(
            job_id=mock_job.id,
            status="completed",
            error_message=pytest.any,
            completed_at=pytest.any,
            articles_found=0,
            articles_saved=0
        )
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.CategoryRepository')
    @patch('src.core.scheduler.tasks._execute_crawl_with_tracking')
    def test_rate_limit_error_with_retry(
        self,
        mock_execute_crawl,
        mock_category_repo,
        mock_job_repo,
        mock_get_settings,
        mock_category,
        mock_job,
        mock_settings
    ):
        """Test rate limit error handling with retry logic."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.update_status = AsyncMock(return_value=True)
        
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=mock_category)
        
        # Mock rate limit error
        mock_execute_crawl.side_effect = RateLimitExceededError("Rate limit exceeded")
        
        # Create mock task instance with retry capability
        mock_task = MagicMock()
        mock_task.request.id = "test-task-id"
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        mock_task.retry = MagicMock(side_effect=Exception("Retry called"))  # Simulate retry
        
        # Execute task - should raise retry exception
        with pytest.raises(Exception, match="Retry called"):
            asyncio.run(
                crawl_category_task(
                    mock_task,
                    str(mock_category.id),
                    str(mock_job.id)
                )
            )
        
        # Verify retry was called with appropriate countdown
        mock_task.retry.assert_called_once()
        retry_kwargs = mock_task.retry.call_args[1]
        assert retry_kwargs["countdown"] >= 900  # Should be at least 15 minutes for rate limit


class TestCleanupOldJobsTask:
    """Test cases for cleanup_old_jobs_task."""
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    def test_successful_cleanup(self, mock_job_repo, mock_get_settings, mock_settings):
        """Test successful job cleanup execution."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.cleanup_old_jobs = AsyncMock(return_value=15)  # 15 jobs cleaned
        job_repo_instance.reset_stuck_jobs = AsyncMock(return_value=2)   # 2 stuck jobs reset
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "cleanup-task-id"
        mock_task.request.retries = 0
        
        # Execute task
        result = asyncio.run(cleanup_old_jobs_task(mock_task))
        
        # Verify results
        assert result["status"] == "completed"
        assert result["jobs_cleaned"] == 15
        assert result["stuck_jobs_reset"] == 2
        assert result["cleanup_days"] == 30
        
        # Verify repository methods were called
        job_repo_instance.cleanup_old_jobs.assert_called_once_with(days_old=30)
        job_repo_instance.reset_stuck_jobs.assert_called_once_with(stuck_threshold_hours=2)


class TestMonitorJobHealthTask:
    """Test cases for monitor_job_health_task."""
    
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    def test_healthy_system(self, mock_job_repo):
        """Test health monitoring with healthy system."""
        # Setup mocks
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        
        # Mock healthy system state
        job_repo_instance.get_active_jobs = AsyncMock(return_value=[MagicMock() for _ in range(5)])
        job_repo_instance.get_running_jobs = AsyncMock(return_value=[MagicMock() for _ in range(2)])
        job_repo_instance.get_stuck_jobs = AsyncMock(return_value=[])  # No stuck jobs
        job_repo_instance.get_job_statistics = AsyncMock(return_value={
            "status_counts": {"completed": 45, "failed": 5}
        })
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "health-task-id"
        
        # Execute task
        result = asyncio.run(monitor_job_health_task(mock_task))
        
        # Verify results
        assert result["status"] == "completed"
        assert result["health_status"] == "healthy"
        assert result["active_jobs"] == 5
        assert result["running_jobs"] == 2
        assert result["stuck_jobs"] == 0
        assert len(result["health_issues"]) == 0
    
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    def test_degraded_system_with_stuck_jobs(self, mock_job_repo):
        """Test health monitoring with stuck jobs (degraded system)."""
        # Setup mocks
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        
        # Mock degraded system state
        job_repo_instance.get_active_jobs = AsyncMock(return_value=[MagicMock() for _ in range(10)])
        job_repo_instance.get_running_jobs = AsyncMock(return_value=[MagicMock() for _ in range(3)])
        job_repo_instance.get_stuck_jobs = AsyncMock(return_value=[MagicMock() for _ in range(2)])  # 2 stuck jobs
        job_repo_instance.get_job_statistics = AsyncMock(return_value={
            "status_counts": {"completed": 30, "failed": 10}
        })
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "health-task-id"
        
        # Execute task
        result = asyncio.run(monitor_job_health_task(mock_task))
        
        # Verify results
        assert result["status"] == "completed"
        assert result["health_status"] == "degraded"
        assert result["stuck_jobs"] == 2
        assert any("stuck" in issue for issue in result["health_issues"])


class TestTriggerCategoryCrawlTask:
    """Test cases for trigger_category_crawl_task."""
    
    @patch('src.core.scheduler.tasks.CategoryRepository')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.crawl_category_task')
    def test_successful_trigger(
        self,
        mock_crawl_task,
        mock_job_repo,
        mock_category_repo,
        mock_category,
        mock_job
    ):
        """Test successful category crawl triggering."""
        # Setup mocks
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=mock_category)
        
        job_repo_instance = AsyncMock()
        mock_job_repo.return_value = job_repo_instance
        job_repo_instance.create_job = AsyncMock(return_value=mock_job)
        
        # Mock Celery task delay method
        mock_result = MagicMock()
        mock_result.id = "celery-task-123"
        mock_crawl_task.delay = MagicMock(return_value=mock_result)
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "trigger-task-id"
        
        # Execute task
        result = asyncio.run(
            trigger_category_crawl_task(
                mock_task,
                str(mock_category.id),
                priority=5,
                metadata={"source": "manual"}
            )
        )
        
        # Verify results
        assert result["status"] == "scheduled"
        assert result["job_id"] == str(mock_job.id)
        assert result["category_name"] == mock_category.name
        assert result["celery_task_id"] == "celery-task-123"
        assert result["priority"] == 5
        
        # Verify job was created
        job_repo_instance.create_job.assert_called_once_with(
            category_id=mock_category.id,
            priority=5,
            correlation_id=pytest.any,
            metadata={"source": "manual"}
        )
        
        # Verify crawl task was scheduled
        mock_crawl_task.delay.assert_called_once_with(
            category_id=str(mock_category.id),
            job_id=str(mock_job.id)
        )
    
    @patch('src.core.scheduler.tasks.CategoryRepository')
    def test_trigger_nonexistent_category(self, mock_category_repo):
        """Test triggering crawl for non-existent category."""
        # Setup mocks
        category_repo_instance = AsyncMock()
        mock_category_repo.return_value = category_repo_instance
        category_repo_instance.get_by_id = AsyncMock(return_value=None)  # Category not found
        
        # Create mock task instance
        mock_task = MagicMock()
        mock_task.request.id = "trigger-task-id"
        
        # Execute task
        result = asyncio.run(
            trigger_category_crawl_task(
                mock_task,
                str(uuid4()),
                priority=0
            )
        )
        
        # Verify results
        assert result["status"] == "failed"
        assert "not found" in result["error"]


@pytest.mark.asyncio
class TestTaskIntegration:
    """Integration tests for task workflows."""
    
    async def test_complete_crawl_workflow(self):
        """Test complete workflow from job creation to completion."""
        # This would be an integration test that tests the complete flow
        # For now, it's a placeholder that would require actual database setup
        pass
    
    async def test_error_recovery_workflow(self):
        """Test error recovery and retry workflows."""
        # This would test the complete error handling and retry logic
        # For now, it's a placeholder that would require actual Celery setup
        pass