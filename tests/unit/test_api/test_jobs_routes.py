"""Tests for jobs API routes.

This module tests the jobs API endpoints including:
- Job priority management (PATCH /jobs/{id}/priority)
- Job configuration updates (PUT /jobs/{id})
- Job deletion (DELETE /jobs/{id})
- Existing job creation and listing functionality

Tests cover success cases, error handling, and edge cases with proper mocking.
"""

import pytest
import uuid
import json
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import status

from src.api.main import app
from src.api.routes.jobs import router
from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from src.database.models.category import Category


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "category_id": str(uuid.uuid4()),
        "status": CrawlJobStatus.PENDING,
        "celery_task_id": "test-task-123",
        "started_at": None,
        "completed_at": None,
        "articles_found": 0,
        "articles_saved": 0,
        "error_message": None,
        "retry_count": 0,
        "priority": 0,
        "correlation_id": "test-correlation-123",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "job_metadata": {"source": "test"}
    }


@pytest.fixture
def sample_category_data():
    """Sample category data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Category",
        "is_active": True,
        "keywords": ["python", "ai"],
        "exclude_keywords": []
    }


@pytest.fixture
def sample_running_job_data(sample_job_data):
    """Sample running job data for testing."""
    running_job = sample_job_data.copy()
    running_job.update({
        "status": CrawlJobStatus.RUNNING,
        "started_at": datetime.now(timezone.utc),
        "articles_found": 5,
        "articles_saved": 3
    })
    return running_job


class TestJobsPriorityAPI:
    """Test class for job priority management endpoints."""

    def test_update_job_priority_success(self, client, sample_job_data, sample_category_data):
        """Test successful job priority update."""
        job_id = sample_job_data["id"]
        category_id = sample_job_data["category_id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo, \
             patch('src.api.routes.jobs.CategoryRepository') as mock_category_repo:

            # Mock repositories
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_category_repo_instance = AsyncMock()
            mock_category_repo.return_value = mock_category_repo_instance

            # Mock updated job with new priority
            updated_job_data = sample_job_data.copy()
            updated_job_data["priority"] = 8
            mock_job_repo_instance.update_job_priority.return_value = Mock(**updated_job_data)

            # Mock category lookup
            mock_category_repo_instance.get_by_id.return_value = Mock(**sample_category_data)

            # Test priority update
            response = client.patch(
                f"/api/v1/jobs/{job_id}/priority",
                json={"priority": 8}
            )

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == job_id
            assert data["priority"] == 8
            assert data["category_name"] == sample_category_data["name"]

            # Verify repository was called correctly
            mock_job_repo_instance.update_job_priority.assert_called_once()
            call_args = mock_job_repo_instance.update_job_priority.call_args
            assert str(call_args[1]["job_id"]) == job_id
            assert call_args[1]["priority"] == 8

    def test_update_job_priority_job_not_found(self, client):
        """Test priority update with non-existent job ID."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock job not found
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.update_job_priority.side_effect = ValueError(f"Job {job_id} not found")

            # Test with non-existent job_id
            response = client.patch(
                f"/api/v1/jobs/{job_id}/priority",
                json={"priority": 5}
            )

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]

    def test_update_job_priority_invalid_priority(self, client):
        """Test priority update with invalid priority value."""
        job_id = str(uuid.uuid4())

        # Test with invalid priority (out of range)
        response = client.patch(
            f"/api/v1/jobs/{job_id}/priority",
            json={"priority": -1}  # Invalid priority
        )

        # Verify validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_job_priority_running_job(self, client, sample_running_job_data):
        """Test priority update fails for running job."""
        job_id = sample_running_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock running job cannot be updated
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.update_job_priority.side_effect = ValueError(
                "Cannot update priority of running job"
            )

            # Test priority update on running job
            response = client.patch(
                f"/api/v1/jobs/{job_id}/priority",
                json={"priority": 8}
            )

            # Verify 400 response
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot update priority" in response.json()["detail"]

    def test_update_job_priority_server_error(self, client):
        """Test priority update with server error."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock server error
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.update_job_priority.side_effect = Exception("Database error")

            # Test priority update
            response = client.patch(
                f"/api/v1/jobs/{job_id}/priority",
                json={"priority": 5}
            )

            # Verify 500 response
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to update job priority" in response.json()["detail"]


class TestJobsConfigurationAPI:
    """Test class for job configuration update endpoints."""

    def test_update_job_success(self, client, sample_job_data, sample_category_data):
        """Test successful job configuration update."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo, \
             patch('src.api.routes.jobs.CategoryRepository') as mock_category_repo:

            # Mock repositories
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_category_repo_instance = AsyncMock()
            mock_category_repo.return_value = mock_category_repo_instance

            # Mock updated job
            updated_job_data = sample_job_data.copy()
            updated_job_data["priority"] = 7
            updated_job_data["retry_count"] = 2
            updated_job_data["job_metadata"] = {"updated": True}
            mock_job_repo_instance.update_job.return_value = Mock(**updated_job_data)

            # Mock category lookup
            mock_category_repo_instance.get_by_id.return_value = Mock(**sample_category_data)

            # Test job update
            update_data = {
                "priority": 7,
                "retry_count": 2,
                "job_metadata": {"updated": True}
            }
            response = client.put(f"/api/v1/jobs/{job_id}", json=update_data)

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == job_id
            assert data["priority"] == 7
            assert data["retry_count"] == 2

            # Verify repository was called correctly
            mock_job_repo_instance.update_job.assert_called_once()
            call_args = mock_job_repo_instance.update_job.call_args
            assert str(call_args[1]["job_id"]) == job_id
            assert call_args[1]["updates"]["priority"] == 7
            assert call_args[1]["updates"]["retry_count"] == 2

    def test_update_job_partial_update(self, client, sample_job_data, sample_category_data):
        """Test partial job configuration update."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo, \
             patch('src.api.routes.jobs.CategoryRepository') as mock_category_repo:

            # Mock repositories
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_category_repo_instance = AsyncMock()
            mock_category_repo.return_value = mock_category_repo_instance

            # Mock updated job with only priority changed
            updated_job_data = sample_job_data.copy()
            updated_job_data["priority"] = 3
            mock_job_repo_instance.update_job.return_value = Mock(**updated_job_data)

            # Mock category lookup
            mock_category_repo_instance.get_by_id.return_value = Mock(**sample_category_data)

            # Test partial update (only priority)
            update_data = {"priority": 3}
            response = client.put(f"/api/v1/jobs/{job_id}", json=update_data)

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["priority"] == 3

            # Verify only priority was in updates
            call_args = mock_job_repo_instance.update_job.call_args
            updates = call_args[1]["updates"]
            assert "priority" in updates
            assert "retry_count" not in updates
            assert "job_metadata" not in updates

    def test_update_job_no_fields_provided(self, client):
        """Test job update with no valid fields."""
        job_id = str(uuid.uuid4())

        # Test with empty update data
        response = client.put(f"/api/v1/jobs/{job_id}", json={})

        # Verify 400 response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No valid fields provided" in response.json()["detail"]

    def test_update_job_not_found(self, client):
        """Test job update with non-existent job ID."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock job not found
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.update_job.side_effect = ValueError(f"Job {job_id} not found")

            # Test with non-existent job_id
            response = client.put(
                f"/api/v1/jobs/{job_id}",
                json={"priority": 5}
            )

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]

    def test_update_job_running_job_restriction(self, client, sample_running_job_data):
        """Test job update fails for running job."""
        job_id = sample_running_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock running job cannot be updated
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.update_job.side_effect = ValueError(
                "Cannot update configuration of running job"
            )

            # Test update on running job
            response = client.put(
                f"/api/v1/jobs/{job_id}",
                json={"priority": 5}
            )

            # Verify 400 response
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot update configuration" in response.json()["detail"]


class TestJobsDeletionAPI:
    """Test class for job deletion endpoints."""

    def test_delete_job_success(self, client, sample_job_data):
        """Test successful job deletion."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock successful deletion
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            mock_impact = {
                "articles_affected": 15,
                "articles_orphaned": 3,
                "celery_task_cancelled": True
            }
            mock_job_repo_instance.delete_job.return_value = mock_impact

            # Test job deletion
            response = client.delete(f"/api/v1/jobs/{job_id}")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["job_id"] == job_id
            assert data["impact"]["articles_affected"] == 15
            assert data["impact"]["articles_orphaned"] == 3
            assert data["message"] == "Job deleted successfully"
            assert "deleted_at" in data

            # Verify repository was called correctly
            mock_job_repo_instance.delete_job.assert_called_once()
            call_args = mock_job_repo_instance.delete_job.call_args
            assert str(call_args[1]["job_id"]) == job_id
            assert call_args[1]["force"] == False  # Default
            assert call_args[1]["delete_articles"] == False  # Default

    def test_delete_job_with_force_flag(self, client, sample_running_job_data):
        """Test job deletion with force flag for running job."""
        job_id = sample_running_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock forced deletion
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            mock_impact = {
                "articles_affected": 10,
                "articles_orphaned": 0,
                "celery_task_cancelled": True,
                "forced_termination": True
            }
            mock_job_repo_instance.delete_job.return_value = mock_impact

            # Test forced job deletion
            deletion_config = {
                "force": True,
                "delete_articles": False
            }
            response = client.delete(
                f"/api/v1/jobs/{job_id}",
                json=deletion_config
            )

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["impact"]["forced_termination"] == True

            # Verify force flag was passed
            call_args = mock_job_repo_instance.delete_job.call_args
            assert call_args[1]["force"] == True

    def test_delete_job_with_articles(self, client, sample_job_data):
        """Test job deletion with articles deletion."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock deletion with articles
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            mock_impact = {
                "articles_affected": 20,
                "articles_deleted": 20,
                "articles_orphaned": 0,
                "celery_task_cancelled": True
            }
            mock_job_repo_instance.delete_job.return_value = mock_impact

            # Test job deletion with articles
            deletion_config = {
                "force": False,
                "delete_articles": True
            }
            response = client.delete(
                f"/api/v1/jobs/{job_id}",
                json=deletion_config
            )

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["impact"]["articles_deleted"] == 20
            assert data["impact"]["articles_orphaned"] == 0

            # Verify delete_articles flag was passed
            call_args = mock_job_repo_instance.delete_job.call_args
            assert call_args[1]["delete_articles"] == True

    def test_delete_job_not_found(self, client):
        """Test job deletion with non-existent job ID."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock job not found
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.delete_job.side_effect = ValueError(f"Job {job_id} not found")

            # Test with non-existent job_id
            response = client.delete(f"/api/v1/jobs/{job_id}")

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]

    def test_delete_running_job_without_force(self, client, sample_running_job_data):
        """Test deletion of running job without force flag fails."""
        job_id = sample_running_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock cannot delete running job without force
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.delete_job.side_effect = ValueError(
                "Cannot delete running job without force flag"
            )

            # Test deletion without force
            response = client.delete(f"/api/v1/jobs/{job_id}")

            # Verify 400 response
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Cannot delete running job" in response.json()["detail"]

    def test_delete_job_server_error(self, client):
        """Test job deletion with server error."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock server error
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.delete_job.side_effect = Exception("Database error")

            # Test job deletion
            response = client.delete(f"/api/v1/jobs/{job_id}")

            # Verify 500 response
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to delete job" in response.json()["detail"]


class TestJobsExistingAPI:
    """Test class for existing job API endpoints to ensure they still work."""

    def test_create_job_success(self, client, sample_category_data):
        """Test successful job creation."""
        category_id = sample_category_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo, \
             patch('src.api.routes.jobs.CategoryRepository') as mock_category_repo, \
             patch('src.api.routes.jobs.trigger_category_crawl_task') as mock_task:

            # Mock repositories and task
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_category_repo_instance = AsyncMock()
            mock_category_repo.return_value = mock_category_repo_instance

            # Mock category lookup
            mock_category_repo_instance.get_by_id.return_value = Mock(**sample_category_data)

            # Mock job creation
            job_data = {
                "id": str(uuid.uuid4()),
                "category_id": category_id,
                "status": CrawlJobStatus.PENDING,
                "priority": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            mock_job_repo_instance.create_job.return_value = Mock(**job_data)
            mock_job_repo_instance.get_by_id.return_value = Mock(**job_data)

            # Mock Celery task
            mock_task.delay.return_value = Mock(id="celery-task-123")

            # Test job creation
            create_data = {
                "category_id": category_id,
                "priority": 0
            }
            response = client.post("/api/v1/jobs", json=create_data)

            # Verify response
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["category_id"] == category_id
            assert data["category_name"] == sample_category_data["name"]

    def test_list_jobs_success(self, client, sample_job_data, sample_category_data):
        """Test successful job listing."""
        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo, \
             patch('src.api.routes.jobs.CategoryRepository') as mock_category_repo:

            # Mock repositories
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_category_repo_instance = AsyncMock()
            mock_category_repo.return_value = mock_category_repo_instance

            # Mock job retrieval
            mock_job_repo_instance.get_active_jobs.return_value = [Mock(**sample_job_data)]

            # Mock category lookup
            mock_category_repo_instance.get_by_id.return_value = Mock(**sample_category_data)

            # Test job listing
            response = client.get("/api/v1/jobs")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "jobs" in data
            assert "total" in data
            assert len(data["jobs"]) == 1

    def test_get_job_status_success(self, client, sample_job_data):
        """Test successful job status retrieval."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.jobs.CrawlJobRepository') as mock_job_repo:
            # Mock repository
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.get_by_id.return_value = Mock(**sample_job_data)

            # Test job status
            response = client.get(f"/api/v1/jobs/{job_id}/status")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == job_id
            assert data["status"] == sample_job_data["status"]