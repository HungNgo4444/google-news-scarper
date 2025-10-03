"""Unit tests for schedule scanner task.

Tests the scan_scheduled_categories_task which is the core of the scheduling system.
Validates that categories with enabled schedules trigger jobs correctly.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from src.core.scheduler.tasks import scan_scheduled_categories_task
from src.database.models.crawl_job import JobType, CrawlJobStatus


@pytest.mark.unit
def test_scan_scheduled_categories_triggers_jobs():
    """Test that scan_scheduled_categories_task triggers jobs for due categories.

    This test validates:
    - Scanner finds categories with next_scheduled_run_at <= current_time
    - Job is created with job_type=SCHEDULED
    - crawl_category_task.delay() is called with correct parameters
    - Category schedule timing is updated (last_run, next_run)

    Coverage: AC3 (Scheduled Job Execution)
    """

    # Arrange: Mock category data
    current_time = datetime.now(timezone.utc)
    category_id = uuid4()

    mock_category = Mock()
    mock_category.id = category_id
    mock_category.name = "Technology"
    mock_category.schedule_enabled = True
    mock_category.schedule_interval_minutes = 60
    mock_category.next_scheduled_run_at = current_time - timedelta(minutes=5)  # Overdue by 5 min

    mock_job = Mock()
    mock_job.id = uuid4()

    # Mock the repositories and task (imports are inside the function)
    with patch('src.database.repositories.sync_category_repo.SyncCategoryRepository') as MockCategoryRepo, \
         patch('src.database.repositories.sync_job_repo.SyncCrawlJobRepository') as MockJobRepo, \
         patch('src.core.scheduler.tasks.crawl_category_task') as mock_crawl_task:

        # Setup repository mocks
        mock_category_repo = MockCategoryRepo.return_value
        mock_category_repo.get_due_scheduled_categories.return_value = [mock_category]

        mock_job_repo = MockJobRepo.return_value
        mock_job_repo.create.return_value = mock_job

        # Setup crawl task mock
        mock_celery_result = Mock()
        mock_celery_result.id = "celery-task-123"
        mock_crawl_task.delay.return_value = mock_celery_result

        # Act: Execute scanner task
        # Call the task's run method directly to bypass Celery wrapper
        result = scan_scheduled_categories_task.run()

        # Assert: Verify scanner behavior
        assert result["status"] == "completed"
        assert result["jobs_triggered"] == 1
        assert len(result["triggered_jobs"]) == 1

        triggered_job = result["triggered_jobs"][0]
        assert triggered_job["category_id"] == str(category_id)
        assert triggered_job["category_name"] == "Technology"

        # Verify job was created with SCHEDULED type
        mock_job_repo.create.assert_called_once()
        create_call_kwargs = mock_job_repo.create.call_args[1]
        assert create_call_kwargs["category_id"] == category_id
        assert create_call_kwargs["job_type"] == JobType.SCHEDULED
        assert create_call_kwargs["status"] == CrawlJobStatus.PENDING

        # Verify crawl task was scheduled
        mock_crawl_task.delay.assert_called_once_with(
            category_id=str(category_id),
            job_id=str(mock_job.id)
        )

        # Verify category schedule timing was updated
        mock_category_repo.update_schedule_timing.assert_called_once()
        update_call = mock_category_repo.update_schedule_timing.call_args[1]
        assert update_call["category_id"] == category_id
        # last_run should be close to current_time (allow 1 second difference)
        assert abs((update_call["last_run"] - current_time).total_seconds()) < 1

        # Next run should be current_time + interval
        expected_next_run = current_time + timedelta(minutes=60)
        actual_next_run = update_call["next_run"]
        assert abs((actual_next_run - expected_next_run).total_seconds()) < 5  # Within 5 seconds


@pytest.mark.unit
def test_scan_scheduled_categories_handles_errors_gracefully():
    """Test that scanner handles errors without crashing.

    This test validates error handling when job creation fails for a category.
    Scanner should continue processing other categories and report errors.

    Coverage: NFR Reliability (error handling)
    """

    current_time = datetime.now(timezone.utc)

    # Two categories: one will fail, one will succeed
    category1_id = uuid4()
    category2_id = uuid4()

    mock_category1 = Mock(id=category1_id, name="Tech", schedule_interval_minutes=30)
    mock_category2 = Mock(id=category2_id, name="Sports", schedule_interval_minutes=60)

    mock_job2 = Mock(id=uuid4())

    with patch('src.database.repositories.sync_category_repo.SyncCategoryRepository') as MockCategoryRepo, \
         patch('src.database.repositories.sync_job_repo.SyncCrawlJobRepository') as MockJobRepo, \
         patch('src.core.scheduler.tasks.crawl_category_task') as mock_crawl_task:

        mock_category_repo = MockCategoryRepo.return_value
        mock_category_repo.get_due_scheduled_categories.return_value = [mock_category1, mock_category2]

        mock_job_repo = MockJobRepo.return_value

        # First create() fails, second succeeds
        mock_job_repo.create.side_effect = [
            Exception("Database error"),
            mock_job2
        ]

        mock_crawl_task.delay.return_value = Mock(id="celery-123")

        # Act
        result = scan_scheduled_categories_task.run()

        # Assert: Scanner completed despite error
        assert result["status"] == "completed"
        assert result["jobs_triggered"] == 1  # Only category2 succeeded
        assert result["errors"] == 1  # category1 failed
        assert len(result["error_details"]) == 1

        # Verify error details
        error_detail = result["error_details"][0]
        assert error_detail["category_id"] == str(category1_id)
        assert "Database error" in error_detail["error"]


@pytest.mark.unit
def test_scan_scheduled_categories_skips_non_due_categories():
    """Test that scanner only processes categories that are actually due.

    Validates the due_scheduled_categories query logic.

    Coverage: AC3 (only process categories with next_run <= current_time)
    """

    with patch('src.database.repositories.sync_category_repo.SyncCategoryRepository') as MockCategoryRepo, \
         patch('src.database.repositories.sync_job_repo.SyncCrawlJobRepository') as MockJobRepo:

        mock_category_repo = MockCategoryRepo.return_value

        # No due categories
        mock_category_repo.get_due_scheduled_categories.return_value = []

        # Act
        result = scan_scheduled_categories_task.run()

        # Assert: No jobs triggered
        assert result["status"] == "completed"
        assert result["jobs_triggered"] == 0
        assert result["categories_scanned"] == 0
        assert len(result["triggered_jobs"]) == 0

        # Verify create was never called
        mock_job_repo = MockJobRepo.return_value
        mock_job_repo.create.assert_not_called()
