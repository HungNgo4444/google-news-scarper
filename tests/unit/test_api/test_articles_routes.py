"""Tests for articles API routes (Story 2.1).

This module tests the new articles API endpoints including:
- Article listing with job filtering
- Article search and pagination
- Article export functionality
- Article statistics
"""

import pytest
import uuid
import json
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import status

from src.api.main import app
from src.api.routes.articles import router
from src.database.models.article import Article
from src.database.models.crawl_job import CrawlJob
from src.services.articlesService import ArticleResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_article_data():
    """Sample article data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "title": "Test Article",
        "content": "This is test content",
        "author": "Test Author",
        "publish_date": "2025-09-15T10:00:00Z",
        "source_url": "https://example.com/article",
        "image_url": "https://example.com/image.jpg",
        "url_hash": "abc123hash",
        "content_hash": "def456hash",
        "last_seen": "2025-09-15T10:00:00Z",
        "crawl_job_id": str(uuid.uuid4()),
        "keywords_matched": ["python", "ai"],
        "relevance_score": 0.85,
        "created_at": "2025-09-15T09:00:00Z",
        "updated_at": "2025-09-15T10:00:00Z"
    }


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "category_id": str(uuid.uuid4()),
        "status": "completed",
        "articles_found": 5,
        "articles_saved": 4
    }


class TestArticlesAPI:
    """Test class for articles API endpoints."""

    def test_list_articles_success(self, client, sample_article_data):
        """Test successful article listing."""
        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository instance and method
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_articles_paginated.return_value = ([Mock(**sample_article_data)], 1)

            # Test GET /api/v1/articles
            response = client.get("/api/v1/articles")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "articles" in data
            assert "total" in data
            assert "page" in data
            assert "size" in data
            assert "pages" in data

    def test_list_articles_with_job_filter(self, client, sample_article_data, sample_job_data):
        """Test article listing with job ID filter."""
        job_id = sample_job_data["id"]

        with patch('src.api.routes.articles.ArticleRepository') as mock_article_repo, \
             patch('src.api.routes.articles.CrawlJobRepository') as mock_job_repo:

            # Mock repositories
            mock_article_repo_instance = AsyncMock()
            mock_article_repo.return_value = mock_article_repo_instance
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            # Mock job exists
            mock_job_repo_instance.get_by_id.return_value = Mock(**sample_job_data)

            # Mock articles retrieval
            mock_article_repo_instance.get_articles_paginated.return_value = (
                [Mock(**sample_article_data)], 1
            )

            # Test with job_id filter
            response = client.get(f"/api/v1/articles?job_id={job_id}")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1

            # Verify job validation was called
            mock_job_repo_instance.get_by_id.assert_called_once()

    def test_list_articles_job_not_found(self, client):
        """Test article listing with non-existent job ID."""
        job_id = str(uuid.uuid4())

        with patch('src.api.routes.articles.CrawlJobRepository') as mock_job_repo:
            # Mock job not found
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance
            mock_job_repo_instance.get_by_id.return_value = None

            # Test with non-existent job_id
            response = client.get(f"/api/v1/articles?job_id={job_id}")

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]

    def test_list_articles_with_search(self, client, sample_article_data):
        """Test article listing with search query."""
        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_articles_paginated.return_value = ([Mock(**sample_article_data)], 1)

            # Test with search query
            response = client.get("/api/v1/articles?search=python")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1

            # Verify search filter was passed
            mock_repo.get_articles_paginated.assert_called_once()
            call_args = mock_repo.get_articles_paginated.call_args
            assert 'search_query' in call_args[1]['filters']
            assert call_args[1]['filters']['search_query'] == 'python'

    def test_list_articles_with_pagination(self, client, sample_article_data):
        """Test article listing with pagination parameters."""
        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_articles_paginated.return_value = ([Mock(**sample_article_data)], 10)

            # Test with pagination
            response = client.get("/api/v1/articles?page=2&size=5")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["page"] == 2
            assert data["size"] == 5
            assert data["pages"] == 2  # ceil(10/5)

    def test_get_article_success(self, client, sample_article_data):
        """Test successful single article retrieval."""
        article_id = sample_article_data["id"]

        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_by_id.return_value = Mock(**sample_article_data)

            # Test GET /api/v1/articles/{article_id}
            response = client.get(f"/api/v1/articles/{article_id}")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == article_id
            assert data["title"] == sample_article_data["title"]

    def test_get_article_not_found(self, client):
        """Test single article retrieval with non-existent ID."""
        article_id = str(uuid.uuid4())

        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_by_id.return_value = None

            # Test with non-existent article_id
            response = client.get(f"/api/v1/articles/{article_id}")

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_export_articles_json(self, client, sample_article_data, sample_job_data):
        """Test article export in JSON format."""
        export_request = {
            "job_id": sample_job_data["id"],
            "format": "json"
        }

        with patch('src.api.routes.articles.ArticleRepository') as mock_article_repo, \
             patch('src.api.routes.articles.CrawlJobRepository') as mock_job_repo:

            # Mock repositories
            mock_article_repo_instance = AsyncMock()
            mock_article_repo.return_value = mock_article_repo_instance
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            # Mock job exists
            mock_job_repo_instance.get_by_id.return_value = Mock(**sample_job_data)

            # Mock articles retrieval
            mock_article_repo_instance.get_articles_paginated.return_value = (
                [Mock(**sample_article_data)], 1
            )

            # Test export
            response = client.post("/api/v1/articles/export", json=export_request)

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"
            assert "attachment" in response.headers["content-disposition"]

    def test_export_articles_csv(self, client, sample_article_data, sample_job_data):
        """Test article export in CSV format."""
        export_request = {
            "job_id": sample_job_data["id"],
            "format": "csv"
        }

        with patch('src.api.routes.articles.ArticleRepository') as mock_article_repo, \
             patch('src.api.routes.articles.CrawlJobRepository') as mock_job_repo:

            # Mock repositories
            mock_article_repo_instance = AsyncMock()
            mock_article_repo.return_value = mock_article_repo_instance
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            # Mock job exists
            mock_job_repo_instance.get_by_id.return_value = Mock(**sample_job_data)

            # Mock articles retrieval
            mock_article_repo_instance.get_articles_paginated.return_value = (
                [Mock(**sample_article_data)], 1
            )

            # Test export
            response = client.post("/api/v1/articles/export", json=export_request)

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/csv"

    def test_export_articles_no_results(self, client, sample_job_data):
        """Test article export with no matching articles."""
        export_request = {
            "job_id": sample_job_data["id"],
            "format": "json"
        }

        with patch('src.api.routes.articles.ArticleRepository') as mock_article_repo, \
             patch('src.api.routes.articles.CrawlJobRepository') as mock_job_repo:

            # Mock repositories
            mock_article_repo_instance = AsyncMock()
            mock_article_repo.return_value = mock_article_repo_instance
            mock_job_repo_instance = AsyncMock()
            mock_job_repo.return_value = mock_job_repo_instance

            # Mock job exists
            mock_job_repo_instance.get_by_id.return_value = Mock(**sample_job_data)

            # Mock no articles found
            mock_article_repo_instance.get_articles_paginated.return_value = ([], 0)

            # Test export
            response = client.post("/api/v1/articles/export", json=export_request)

            # Verify 404 response
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_export_articles_invalid_format(self, client, sample_job_data):
        """Test article export with invalid format."""
        export_request = {
            "job_id": sample_job_data["id"],
            "format": "xml"  # Invalid format
        }

        # Test export with invalid format
        response = client.post("/api/v1/articles/export", json=export_request)

        # Verify validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_article_stats(self, client):
        """Test article statistics endpoint."""
        mock_stats = {
            "total_articles": 100,
            "articles_by_job": {"job1": 25, "job2": 35},
            "articles_by_category": {"Tech": 40, "Science": 30},
            "recent_articles_count": 15,
            "average_relevance_score": 0.75
        }

        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_article_statistics.return_value = mock_stats

            # Test GET /api/v1/articles/stats
            response = client.get("/api/v1/articles/stats")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_articles"] == 100
            assert "articles_by_job" in data
            assert "articles_by_category" in data
            assert "recent_articles_count" in data
            assert "average_relevance_score" in data

    def test_list_articles_server_error(self, client):
        """Test article listing with server error."""
        with patch('src.api.routes.articles.ArticleRepository') as mock_repo_class:
            # Mock repository to raise exception
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_articles_paginated.side_effect = Exception("Database error")

            # Test GET /api/v1/articles
            response = client.get("/api/v1/articles")

            # Verify 500 response
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to retrieve articles" in response.json()["detail"]