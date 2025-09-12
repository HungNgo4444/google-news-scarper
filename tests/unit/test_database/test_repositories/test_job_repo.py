"""Tests for CrawlJobRepository operations.

This module tests the CrawlJobRepository class including CRUD operations,
job status tracking, statistics, and cleanup functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

from src.database.repositories.job_repo import CrawlJobRepository
from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from src.database.models.category import Category


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = AsyncMock()
    session.begin = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_category():
    """Sample category for testing."""
    category = Category()
    category.id = uuid4()
    category.name = "Technology"
    category.keywords = ["python", "javascript"]
    category.exclude_keywords = ["jobs"]
    category.is_active = True
    return category


@pytest.fixture
def sample_job(sample_category):
    """Sample crawl job for testing."""
    job = CrawlJob()
    job.id = uuid4()
    job.category_id = sample_category.id
    job.status = CrawlJobStatus.PENDING
    job.priority = 0
    job.articles_found = 0
    job.articles_saved = 0
    job.retry_count = 0
    job.created_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    return job


class TestCrawlJobRepository:
    """Test cases for CrawlJobRepository."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test method."""
        self.repo = CrawlJobRepository()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_create_job_success(self, mock_get_session, mock_db_session, sample_category):
        """Test successful job creation."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock the created job
        created_job = CrawlJob(
            category_id=sample_category.id,
            status=CrawlJobStatus.PENDING,
            priority=5,
            correlation_id="test-correlation",
            metadata={"source": "test"}
        )
        created_job.id = uuid4()
        
        # Mock session operations
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Mock flush and refresh to simulate database operations
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', created_job.id))
        
        # Execute test
        result = await self.repo.create_job(
            category_id=sample_category.id,
            priority=5,
            correlation_id="test-correlation",
            metadata={"source": "test"}
        )
        
        # Verify results
        assert isinstance(result, CrawlJob)
        assert result.category_id == sample_category.id
        assert result.status == CrawlJobStatus.PENDING
        assert result.priority == 5
        assert result.correlation_id == "test-correlation"
        assert result.metadata == {"source": "test"}
        
        # Verify session operations
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_update_status_success(self, mock_get_session, mock_db_session, sample_job):
        """Test successful job status update."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock successful update
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock transaction context
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Execute test
        start_time = datetime.now(timezone.utc)
        success = await self.repo.update_status(
            job_id=sample_job.id,
            status=CrawlJobStatus.RUNNING,
            started_at=start_time,
            celery_task_id="celery-123",
            articles_found=10,
            articles_saved=8,
            correlation_id="test-correlation"
        )
        
        # Verify results
        assert success is True
        
        # Verify database query was executed
        mock_db_session.execute.assert_called_once()
        
        # Get the query that was executed
        call_args = mock_db_session.execute.call_args[0][0]
        # Verify it's an update statement (this is implementation-specific)
        assert hasattr(call_args, 'table')  # Should be an update statement
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_update_status_job_not_found(self, mock_get_session, mock_db_session):
        """Test status update when job is not found."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock no rows affected (job not found)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock transaction context
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Execute test
        success = await self.repo.update_status(
            job_id=uuid4(),  # Non-existent job ID
            status=CrawlJobStatus.COMPLETED
        )
        
        # Verify results
        assert success is False
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_get_active_jobs(self, mock_get_session, mock_db_session):
        """Test retrieving active jobs."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Create mock jobs
        running_job = MagicMock()
        running_job.status = CrawlJobStatus.RUNNING
        running_job.priority = 5
        
        pending_job = MagicMock()
        pending_job.status = CrawlJobStatus.PENDING
        pending_job.priority = 3
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [running_job, pending_job]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute test
        jobs = await self.repo.get_active_jobs(limit=10)
        
        # Verify results
        assert len(jobs) == 2
        assert jobs[0] == running_job
        assert jobs[1] == pending_job
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_get_job_statistics(self, mock_get_session, mock_db_session):
        """Test retrieving job statistics."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock statistics queries
        mock_db_session.execute = AsyncMock()
        
        # Mock status count queries
        status_results = [
            MagicMock(scalar=lambda: 45),  # completed
            MagicMock(scalar=lambda: 5),   # failed
            MagicMock(scalar=lambda: 10),  # running
            MagicMock(scalar=lambda: 20),  # pending
        ]
        
        # Mock metrics query
        metrics_result = MagicMock()
        metrics_result.first.return_value = (150, 120, 15.0, 12.0)  # totals and averages
        
        # Mock duration query
        duration_result = MagicMock()
        duration_result.scalar.return_value = 300.0  # 5 minutes average
        
        # Set up the execute method to return different results based on call order
        mock_db_session.execute.side_effect = status_results + [metrics_result, duration_result]
        
        # Execute test
        stats = await self.repo.get_job_statistics()
        
        # Verify results structure
        assert isinstance(stats, dict)
        assert "status_counts" in stats
        assert "total_articles_found" in stats
        assert "total_articles_saved" in stats
        assert "avg_articles_found" in stats
        assert "avg_articles_saved" in stats
        assert "avg_duration_seconds" in stats
        assert "success_rate" in stats
        assert "generated_at" in stats
        
        # Verify some expected values
        assert stats["avg_duration_seconds"] == 300.0
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_cleanup_old_jobs(self, mock_get_session, mock_db_session):
        """Test cleaning up old jobs."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock successful cleanup
        mock_result = MagicMock()
        mock_result.rowcount = 25  # 25 jobs cleaned
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock transaction context
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Execute test
        cleaned_count = await self.repo.cleanup_old_jobs(days_old=30)
        
        # Verify results
        assert cleaned_count == 25
        
        # Verify database operations
        mock_db_session.execute.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_get_stuck_jobs(self, mock_get_session, mock_db_session):
        """Test retrieving stuck jobs."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Create mock stuck jobs
        stuck_job1 = MagicMock()
        stuck_job1.id = uuid4()
        stuck_job1.status = CrawlJobStatus.RUNNING
        stuck_job1.started_at = datetime.now(timezone.utc) - timedelta(hours=5)
        
        stuck_job2 = MagicMock()
        stuck_job2.id = uuid4()
        stuck_job2.status = CrawlJobStatus.RUNNING
        stuck_job2.started_at = datetime.now(timezone.utc) - timedelta(hours=3)
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_job1, stuck_job2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute test
        stuck_jobs = await self.repo.get_stuck_jobs(stuck_threshold_hours=2)
        
        # Verify results
        assert len(stuck_jobs) == 2
        assert stuck_jobs[0] == stuck_job1
        assert stuck_jobs[1] == stuck_job2
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_reset_stuck_jobs(self, mock_get_session, mock_db_session):
        """Test resetting stuck jobs."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock successful reset
        mock_result = MagicMock()
        mock_result.rowcount = 3  # 3 jobs reset
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock transaction context
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        
        # Execute test
        reset_count = await self.repo.reset_stuck_jobs(stuck_threshold_hours=2)
        
        # Verify results
        assert reset_count == 3
        
        # Verify database operations
        mock_db_session.execute.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_get_jobs_by_category(self, mock_get_session, mock_db_session, sample_category):
        """Test retrieving jobs by category."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Create mock jobs for the category
        job1 = MagicMock()
        job1.category_id = sample_category.id
        job1.status = CrawlJobStatus.COMPLETED
        
        job2 = MagicMock()
        job2.category_id = sample_category.id
        job2.status = CrawlJobStatus.FAILED
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job1, job2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute test
        jobs = await self.repo.get_jobs_by_category(
            category_id=sample_category.id,
            status=None,  # All statuses
            limit=50
        )
        
        # Verify results
        assert len(jobs) == 2
        assert jobs[0] == job1
        assert jobs[1] == job2
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_get_job_by_celery_id(self, mock_get_session, mock_db_session):
        """Test retrieving job by Celery task ID."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Create mock job
        mock_job = MagicMock()
        mock_job.celery_task_id = "celery-123"
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute test
        job = await self.repo.get_job_by_celery_id("celery-123")
        
        # Verify results
        assert job == mock_job
        
        # Verify query was executed
        mock_db_session.execute.assert_called_once()


class TestJobRepositoryEdgeCases:
    """Test edge cases and error conditions for CrawlJobRepository."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test method."""
        self.repo = CrawlJobRepository()
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_create_job_database_error(self, mock_get_session, mock_db_session):
        """Test job creation with database error."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock database error
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        mock_db_session.flush = AsyncMock(side_effect=Exception("Database error"))
        
        # Execute test - should raise exception
        with pytest.raises(Exception, match="Database error"):
            await self.repo.create_job(
                category_id=uuid4(),
                priority=0
            )
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_update_status_database_error(self, mock_get_session, mock_db_session):
        """Test status update with database error."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock database error
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        mock_db_session.execute = AsyncMock(side_effect=Exception("Database error"))
        
        # Execute test - should raise exception
        with pytest.raises(Exception, match="Database error"):
            await self.repo.update_status(
                job_id=uuid4(),
                status=CrawlJobStatus.FAILED
            )
    
    @patch('src.database.repositories.job_repo.get_db_session')
    async def test_cleanup_old_jobs_database_error(self, mock_get_session, mock_db_session):
        """Test cleanup with database error."""
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Mock database error
        mock_db_session.begin.return_value.__aenter__ = AsyncMock()
        mock_db_session.begin.return_value.__aexit__ = AsyncMock()
        mock_db_session.execute = AsyncMock(side_effect=Exception("Database error"))
        
        # Execute test - should raise exception
        with pytest.raises(Exception, match="Database error"):
            await self.repo.cleanup_old_jobs(days_old=30)
    
    async def test_empty_statistics_calculation(self):
        """Test statistics calculation with no data."""
        # This test would verify that statistics methods handle empty datasets gracefully
        # Implementation would depend on actual database setup
        pass


@pytest.mark.asyncio
class TestJobRepositoryIntegration:
    """Integration tests for CrawlJobRepository."""
    
    async def test_complete_job_lifecycle(self):
        """Test complete job lifecycle from creation to completion."""
        # This would be a full integration test with real database
        # For now, it's a placeholder requiring actual database setup
        pass
    
    async def test_concurrent_job_operations(self):
        """Test concurrent job operations and race conditions."""
        # This would test concurrent access patterns
        # For now, it's a placeholder requiring actual database setup
        pass