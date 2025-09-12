"""Integration tests for the complete job scheduler system.

This module provides end-to-end integration tests for the job scheduling system,
testing the complete workflow from job creation through execution to completion.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.scheduler.celery_app import celery_app, check_celery_health
from src.core.scheduler.tasks import (
    crawl_category_task,
    trigger_category_crawl_task,
    cleanup_old_jobs_task,
    monitor_job_health_task
)
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.category_repo import CategoryRepository
from src.database.models.crawl_job import CrawlJobStatus
from src.shared.config import get_settings


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    settings = MagicMock()
    settings.JOB_EXECUTION_TIMEOUT = 1800
    settings.JOB_CLEANUP_DAYS = 30
    settings.CELERY_BROKER_URL = "redis://localhost:6379/0"
    settings.CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
    settings.MAX_CONCURRENT_JOBS = 10
    return settings


@pytest.fixture
def mock_category():
    """Mock category for testing."""
    category = MagicMock()
    category.id = uuid4()
    category.name = "Integration Test Category"
    category.keywords = ["integration", "test", "scheduler"]
    category.exclude_keywords = ["exclude"]
    category.is_active = True
    return category


class TestSchedulerIntegration:
    """Integration tests for the complete scheduler system."""
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.database.repositories.job_repo.get_db_session')
    @patch('src.database.repositories.category_repo.get_db_session')
    def test_complete_job_workflow(self, mock_category_session, mock_job_session, mock_get_settings, test_settings, mock_category):
        """Test complete job workflow from creation to completion."""
        # Setup settings
        mock_get_settings.return_value = test_settings
        
        # Mock database sessions
        job_session = AsyncMock()
        category_session = AsyncMock()
        mock_job_session.return_value.__aenter__.return_value = job_session
        mock_category_session.return_value.__aenter__.return_value = category_session
        
        # Mock category repository operations
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_category
        category_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock job repository operations
        job_session.begin.return_value.__aenter__ = AsyncMock()
        job_session.begin.return_value.__aexit__ = AsyncMock()
        job_session.add = MagicMock()
        job_session.flush = AsyncMock()
        job_session.refresh = AsyncMock()
        
        # Mock successful job updates
        mock_update_result = MagicMock()
        mock_update_result.rowcount = 1
        job_session.execute = AsyncMock(return_value=mock_update_result)
        
        # Mock crawler execution
        with patch('src.core.scheduler.tasks._execute_crawl_with_tracking') as mock_crawl:
            mock_crawl.return_value = (15, 12)  # 15 found, 12 saved
            
            # Create mock task instance
            mock_task = MagicMock()
            mock_task.request.id = "integration-test-task"
            mock_task.request.retries = 0
            
            # Execute the complete workflow
            result = asyncio.run(
                crawl_category_task(
                    mock_task,
                    str(mock_category.id),
                    str(uuid4())  # job_id
                )
            )
        
        # Verify workflow completion
        assert result["status"] == "completed"
        assert result["articles_found"] == 15
        assert result["articles_saved"] == 12
        assert result["category_name"] == mock_category.name
        
        # Verify database operations occurred
        job_session.add.assert_called()
        job_session.flush.assert_called()
    
    @patch('src.core.scheduler.tasks.get_settings')
    def test_celery_health_check_integration(self, mock_get_settings, test_settings):
        """Test Celery health check integration."""
        mock_get_settings.return_value = test_settings
        
        # Test health check function
        health_result = check_celery_health()
        
        # Verify health check structure
        assert isinstance(health_result, dict)
        assert "status" in health_result
        assert "broker" in health_result
        
        # The actual status depends on whether Celery is running
        # In a test environment, it's likely to be unhealthy
        assert health_result["status"] in ["healthy", "unhealthy"]
        assert health_result["broker"] == test_settings.CELERY_BROKER_URL
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.database.repositories.job_repo.get_db_session')
    def test_job_maintenance_workflow(self, mock_job_session, mock_get_settings, test_settings):
        """Test job maintenance and cleanup workflow."""
        mock_get_settings.return_value = test_settings
        
        # Mock database session
        job_session = AsyncMock()
        mock_job_session.return_value.__aenter__.return_value = job_session
        
        # Mock cleanup operations
        job_session.begin.return_value.__aenter__ = AsyncMock()
        job_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Mock cleanup and reset results
        cleanup_result = MagicMock()
        cleanup_result.rowcount = 10  # 10 jobs cleaned
        
        reset_result = MagicMock() 
        reset_result.rowcount = 2   # 2 stuck jobs reset
        
        job_session.execute = AsyncMock(side_effect=[cleanup_result, reset_result])
        
        # Create mock task
        mock_task = MagicMock()
        mock_task.request.id = "cleanup-integration-test"
        mock_task.request.retries = 0
        
        # Execute cleanup workflow
        result = asyncio.run(cleanup_old_jobs_task(mock_task))
        
        # Verify cleanup results
        assert result["status"] == "completed"
        assert result["jobs_cleaned"] == 10
        assert result["stuck_jobs_reset"] == 2
        assert result["cleanup_days"] == test_settings.JOB_CLEANUP_DAYS
    
    @patch('src.database.repositories.job_repo.get_db_session')
    def test_health_monitoring_workflow(self, mock_job_session):
        """Test health monitoring workflow integration."""
        # Mock database session
        job_session = AsyncMock()
        mock_job_session.return_value.__aenter__.return_value = job_session
        
        # Mock health check queries
        # Active jobs query
        active_result = MagicMock()
        active_result.scalars.return_value.all.return_value = [MagicMock() for _ in range(5)]
        
        # Running jobs query
        running_result = MagicMock()
        running_result.scalars.return_value.all.return_value = [MagicMock() for _ in range(2)]
        
        # Stuck jobs query
        stuck_result = MagicMock()
        stuck_result.scalars.return_value.all.return_value = []  # No stuck jobs
        
        # Statistics query results
        stats_results = [
            MagicMock(scalar=lambda: 80),  # completed
            MagicMock(scalar=lambda: 10),  # failed
            MagicMock(scalar=lambda: 2),   # running
            MagicMock(scalar=lambda: 5),   # pending
        ]
        
        # Additional stats queries
        metrics_result = MagicMock()
        metrics_result.first.return_value = (200, 180, 20.0, 18.0)
        
        duration_result = MagicMock()
        duration_result.scalar.return_value = 450.0
        
        # Set up execute method to return appropriate results
        job_session.execute = AsyncMock(side_effect=[
            active_result, running_result, stuck_result
        ] + stats_results + [metrics_result, duration_result])
        
        # Create mock task
        mock_task = MagicMock()
        mock_task.request.id = "health-integration-test"
        
        # Execute health monitoring
        result = asyncio.run(monitor_job_health_task(mock_task))
        
        # Verify health monitoring results
        assert result["status"] == "completed"
        assert result["health_status"] == "healthy"  # No stuck jobs, good success rate
        assert result["active_jobs"] == 5
        assert result["running_jobs"] == 2
        assert result["stuck_jobs"] == 0
        assert len(result["health_issues"]) == 0
        
        # Verify success rate calculation
        expected_success_rate = 80 / (80 + 10)  # completed / (completed + failed)
        assert abs(result["success_rate_24h"] - expected_success_rate) < 0.01
    
    @patch('src.core.scheduler.tasks.CategoryRepository')
    @patch('src.core.scheduler.tasks.CrawlJobRepository')
    @patch('src.core.scheduler.tasks.crawl_category_task')
    def test_trigger_crawl_integration(
        self,
        mock_crawl_task,
        mock_job_repo_class,
        mock_category_repo_class,
        mock_category
    ):
        """Test triggering crawl integration workflow."""
        # Mock repository instances
        category_repo = AsyncMock()
        job_repo = AsyncMock()
        mock_category_repo_class.return_value = category_repo
        mock_job_repo_class.return_value = job_repo
        
        # Mock category retrieval
        category_repo.get_by_id = AsyncMock(return_value=mock_category)
        
        # Mock job creation
        mock_job = MagicMock()
        mock_job.id = uuid4()
        job_repo.create_job = AsyncMock(return_value=mock_job)
        
        # Mock Celery task scheduling
        mock_celery_result = MagicMock()
        mock_celery_result.id = "scheduled-task-123"
        mock_crawl_task.delay = MagicMock(return_value=mock_celery_result)
        
        # Create mock trigger task
        mock_task = MagicMock()
        mock_task.request.id = "trigger-integration-test"
        
        # Execute trigger workflow
        result = asyncio.run(
            trigger_category_crawl_task(
                mock_task,
                str(mock_category.id),
                priority=7,
                metadata={"source": "integration_test"}
            )
        )
        
        # Verify trigger results
        assert result["status"] == "scheduled"
        assert result["job_id"] == str(mock_job.id)
        assert result["category_name"] == mock_category.name
        assert result["celery_task_id"] == "scheduled-task-123"
        assert result["priority"] == 7
        
        # Verify workflow steps
        category_repo.get_by_id.assert_called_once_with(mock_category.id)
        job_repo.create_job.assert_called_once_with(
            category_id=mock_category.id,
            priority=7,
            correlation_id=pytest.any,
            metadata={"source": "integration_test"}
        )
        mock_crawl_task.delay.assert_called_once_with(
            category_id=str(mock_category.id),
            job_id=str(mock_job.id)
        )


class TestSchedulerErrorScenarios:
    """Test error scenarios and recovery in the scheduler system."""
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.database.repositories.job_repo.get_db_session')
    @patch('src.database.repositories.category_repo.get_db_session')
    def test_database_connection_failure(self, mock_category_session, mock_job_session, mock_get_settings, test_settings):
        """Test handling of database connection failures."""
        mock_get_settings.return_value = test_settings
        
        # Mock database connection failure
        mock_job_session.side_effect = Exception("Database connection failed")
        
        # Create mock task
        mock_task = MagicMock()
        mock_task.request.id = "db-failure-test"
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        mock_task.retry = MagicMock(side_effect=Exception("Retry scheduled"))
        
        # Execute task - should attempt retry
        with pytest.raises(Exception, match="Retry scheduled"):
            asyncio.run(
                crawl_category_task(
                    mock_task,
                    str(uuid4()),
                    str(uuid4())
                )
            )
        
        # Verify retry was attempted
        mock_task.retry.assert_called_once()
    
    @patch('src.core.scheduler.tasks.get_settings')
    @patch('src.database.repositories.job_repo.get_db_session')
    def test_cleanup_task_error_recovery(self, mock_job_session, mock_get_settings, test_settings):
        """Test error recovery in cleanup task."""
        mock_get_settings.return_value = test_settings
        
        # Mock database session failure
        job_session = AsyncMock()
        mock_job_session.return_value.__aenter__.return_value = job_session
        job_session.begin.return_value.__aenter__ = AsyncMock()
        job_session.begin.return_value.__aexit__ = AsyncMock()
        job_session.execute = AsyncMock(side_effect=Exception("Cleanup query failed"))
        
        # Create mock task with retry capability
        mock_task = MagicMock()
        mock_task.request.id = "cleanup-error-test"
        mock_task.request.retries = 0
        mock_task.max_retries = 2
        mock_task.retry = MagicMock(side_effect=Exception("Retry scheduled"))
        
        # Execute cleanup task - should attempt retry
        with pytest.raises(Exception, match="Retry scheduled"):
            asyncio.run(cleanup_old_jobs_task(mock_task))
        
        # Verify retry was attempted
        mock_task.retry.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    def test_health_monitoring_partial_failure(self, mock_job_session):
        """Test health monitoring with partial database failures."""
        # Mock database session
        job_session = AsyncMock()
        mock_job_session.return_value.__aenter__.return_value = job_session
        
        # Mock partial failure - some queries succeed, others fail
        successful_result = MagicMock()
        successful_result.scalars.return_value.all.return_value = []
        
        job_session.execute = AsyncMock(side_effect=[
            successful_result,  # active jobs query succeeds
            successful_result,  # running jobs query succeeds
            Exception("Query failed"),  # stuck jobs query fails
        ])
        
        # Create mock task
        mock_task = MagicMock()
        mock_task.request.id = "health-partial-failure-test"
        
        # Execute health monitoring - should handle partial failure gracefully
        result = asyncio.run(monitor_job_health_task(mock_task))
        
        # Verify graceful failure handling
        assert result["status"] == "failed"
        assert "error" in result
        assert "Query failed" in result["error"]


@pytest.mark.integration
class TestSchedulerPerformance:
    """Performance and load testing for the scheduler system."""
    
    def test_concurrent_job_creation(self):
        """Test concurrent job creation performance."""
        # This would test the system under concurrent load
        # For now, it's a placeholder requiring actual infrastructure
        pass
    
    def test_large_job_queue_handling(self):
        """Test handling of large job queues."""
        # This would test system behavior with many queued jobs
        # For now, it's a placeholder requiring actual infrastructure
        pass
    
    def test_memory_usage_during_batch_processing(self):
        """Test memory usage patterns during batch job processing."""
        # This would monitor memory usage during intensive processing
        # For now, it's a placeholder requiring actual infrastructure
        pass


if __name__ == "__main__":
    # Allow running tests directly for development
    pytest.main([__file__, "-v"])