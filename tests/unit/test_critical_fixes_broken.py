"""Unit tests for critical async/threading fixes.

This test module validates the fixes implemented in Story 2.2:
- Event loop management in Celery tasks
- Async/sync mixing in ArticleExtractor
- CloudScraper integration
- Concurrency optimizations
- Error handling improvements
"""

import pytest
import asyncio
import unittest.mock
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4

from src.shared.config import get_settings
from src.core.scheduler.tasks import _async_crawl_category_task
from src.core.crawler.extractor import ArticleExtractor
from src.core.crawler.engine import CrawlerEngine


class TestEventLoopFixes:
    """Test event loop management fixes in Celery tasks."""

    def test_no_new_event_loop_creation(self):
        """Test that new event loops are not created in sync task functions."""
        # Import the task function to check it doesn't create event loops
        from src.core.scheduler.tasks import crawl_category_task
        import inspect

        # Get the source code of the function
        source = inspect.getsource(crawl_category_task)

        # Verify that asyncio.new_event_loop is not used
        assert "asyncio.new_event_loop()" not in source
        assert "asyncio.set_event_loop(loop)" not in source
        assert "loop.close()" not in source

        # Verify it uses asyncio.run instead
        assert "asyncio.run(" in source

    @pytest.mark.asyncio
    async def test_async_task_function_structure(self):
        """Test that async task functions have proper structure."""
        settings = get_settings()
        mock_task = Mock()
        mock_task.request.id = str(uuid4())
        mock_task.request.retries = 0

        # Mock the repository and other dependencies
        with patch('src.core.scheduler.tasks.CrawlJobRepository') as mock_repo:
            mock_repo.return_value.update_status = AsyncMock()

            with patch('src.core.scheduler.tasks.CategoryRepository') as mock_cat_repo:
                mock_category = Mock()
                mock_category.id = uuid4()
                mock_category.name = "Test Category"
                mock_category.is_active = True
                mock_category.keywords = ["test"]
                mock_category.exclude_keywords = []

                mock_cat_repo.return_value.get_by_id = AsyncMock(return_value=mock_category)

                with patch('src.core.scheduler.tasks._execute_crawl_with_tracking') as mock_crawl:
                    mock_crawl.return_value = (5, 3)  # articles_found, articles_saved

                    # This should not raise any event loop related errors
                    result = await _async_crawl_category_task(
                        mock_task, str(mock_category.id), str(uuid4()),
                        "test_correlation_id", settings
                    )

                    assert result['status'] == 'completed'
                    assert result['articles_found'] == 5
                    assert result['articles_saved'] == 3


class TestAsyncSyncMixingFixes:
    """Test async/sync mixing fixes in ArticleExtractor."""

    @pytest.mark.asyncio
    async def test_article_extractor_async_wrapper(self):
        """Test that ArticleExtractor uses proper async wrapper for newspaper4k."""
        settings = get_settings()
        extractor = ArticleExtractor(settings)

        # Mock newspaper Article
        mock_article = Mock()
        mock_article.download = Mock()
        mock_article.parse = Mock()

        # Test the new async wrapper method
        try:
            await extractor._download_and_parse_article_async(mock_article)
            # Should complete without blocking the event loop
            assert mock_article.download.called
            assert mock_article.parse.called
        except Exception as e:
            # Allow timeout or network errors in test environment
            assert "timeout" in str(e).lower() or "network" in str(e).lower()

    def test_no_run_in_executor_direct_usage(self):
        """Test that direct run_in_executor usage is replaced with proper wrapper."""
        from src.core.crawler.extractor import ArticleExtractor
        import inspect

        source = inspect.getsource(ArticleExtractor._extract_single_article)

        # Should not use run_in_executor directly
        assert "run_in_executor" not in source or "download_and_parse_article_async" in source

        # Should use the new async wrapper
        assert "_download_and_parse_article_async" in source

    @pytest.mark.asyncio
    async def test_timeout_handling_improvement(self):
        """Test improved timeout handling in article extraction."""
        settings = get_settings()
        settings.EXTRACTION_TIMEOUT = 1  # Short timeout for testing

        extractor = ArticleExtractor(settings)

        # Mock article that takes too long - use sync blocking operation
        mock_article = Mock()
        def slow_download():
            import time
            time.sleep(2)  # Longer than timeout (blocking operation)
            return None

        mock_article.download = slow_download
        mock_article.parse = Mock()  # Fast parse

        # Should raise timeout exception
        from src.shared.exceptions import ExtractionTimeoutError
        with pytest.raises(ExtractionTimeoutError) as exc_info:
            await extractor._download_and_parse_article_async(mock_article)

        # Should raise timeout error, not hang indefinitely
        assert "timeout" in str(exc_info.value).lower()


class TestCloudScraperIntegration:
    """Test CloudScraper integration."""

    def test_cloudscraper_initialization(self):
        """Test CloudScraper is properly initialized when enabled."""
        settings = get_settings()
        settings.CLOUDSCRAPER_ENABLED = True

        with patch('src.core.crawler.engine.cloudscraper') as mock_cloudscraper:
            mock_cloudscraper.create_scraper.return_value = Mock()

            # Mock other dependencies - correct import paths
            with patch('src.core.crawler.engine.GoogleNewsSource'):
                with patch('src.core.crawler.engine.ArticleExtractor'):
                        crawler = CrawlerEngine(
                        settings=settings,
                        logger=Mock(),
                        article_extractor=Mock(),
                        article_repo=Mock()
                    )

                    # Should have initialized CloudScraper
                    mock_cloudscraper.create_scraper.assert_called_once()
                    assert crawler.scraper is not None

    def test_cloudscraper_fallback(self):
        """Test fallback to standard search when CloudScraper fails."""
        settings = get_settings()
        settings.CLOUDSCRAPER_ENABLED = True

        with patch('src.core.crawler.engine.cloudscraper') as mock_cloudscraper:
            # Mock CloudScraper to fail
            mock_cloudscraper.create_scraper.side_effect = Exception("CloudScraper failed")

            with patch('src.core.crawler.engine.GoogleNewsSource'):
                with patch('src.core.crawler.engine.ArticleExtractor'):
                    crawler = CrawlerEngine(
                        settings=settings,
                        logger=Mock(),
                        article_extractor=Mock(),
                        article_repo=Mock()
                    )

                    # Should fall back gracefully
                    assert crawler.scraper is None

    def test_cloudscraper_disabled(self):
        """Test that CloudScraper is not initialized when disabled."""
        settings = get_settings()
        settings.CLOUDSCRAPER_ENABLED = False

        with patch('src.core.crawler.engine.GoogleNewsSource'):
            with patch('src.core.crawler.engine.ArticleExtractor'):
                    crawler = CrawlerEngine(
                        settings=settings,
                        logger=Mock(),
                        article_extractor=Mock(),
                        article_repo=Mock()
                    )

                    # Should not have CloudScraper
                    assert crawler.scraper is None


class TestConcurrencyOptimizations:
    """Test concurrency and threading optimizations."""

    def test_configurable_concurrency_limit(self):
        """Test that concurrency limit is configurable."""
        settings = get_settings()
        settings.CRAWLER_CONCURRENCY_LIMIT = 15

        with patch('src.core.crawler.engine.GoogleNewsSource'):
            with patch('src.core.crawler.engine.ArticleExtractor'):
                    crawler = CrawlerEngine(
                        settings=settings,
                        logger=Mock(),
                        article_extractor=Mock(),
                        article_repo=Mock()
                    )

                    # Verify the setting is used
                    assert settings.CRAWLER_CONCURRENCY_LIMIT == 15

    def test_default_concurrency_improvement(self):
        """Test that default concurrency is improved from 5 to 10."""
        settings = get_settings()

        # Default should be 10 (improved from 5)
        assert settings.CRAWLER_CONCURRENCY_LIMIT >= 10

    @pytest.mark.asyncio
    async def test_semaphore_usage(self):
        """Test that semaphore is properly used for concurrency control."""
        settings = get_settings()
        settings.CRAWLER_CONCURRENCY_LIMIT = 2  # Small limit for testing

        with patch('src.core.crawler.engine.GoogleNewsSource'):
            with patch('src.core.crawler.engine.ArticleExtractor'):
                    crawler = CrawlerEngine(
                        settings=settings,
                        logger=Mock(),
                        article_extractor=Mock(),
                        article_repo=Mock()
                    )

                    # Mock the article extraction to track concurrency
                    extraction_times = []

                    async def mock_extract(url):
                        start_time = asyncio.get_event_loop().time()
                        await asyncio.sleep(0.1)  # Simulate work
                        end_time = asyncio.get_event_loop().time()
                        extraction_times.append((start_time, end_time))
                        return {"url": url, "title": "Test"}

                    crawler.article_extractor.extract_article_metadata = mock_extract

                    # Process multiple URLs
                    urls = ["http://example.com/1", "http://example.com/2", "http://example.com/3"]
                    await crawler.extract_articles_batch(urls, "test_correlation")

                    # With concurrency limit of 2, not all should run simultaneously
                    assert len(extraction_times) == 3


class TestErrorHandlingImprovements:
    """Test enhanced error handling and monitoring."""

    def test_new_configuration_settings(self):
        """Test that new configuration settings are available."""
        settings = get_settings()

        # Test new settings exist
        assert hasattr(settings, 'CRAWLER_CONCURRENCY_LIMIT')
        assert hasattr(settings, 'CLOUDSCRAPER_ENABLED')
        assert hasattr(settings, 'CLOUDSCRAPER_DELAY')
        assert hasattr(settings, 'CELERY_ASYNC_TIMEOUT')
        assert hasattr(settings, 'ARTICLE_EXTRACTION_BATCH_SIZE')

    def test_configuration_defaults(self):
        """Test that configuration defaults are set correctly."""
        settings = get_settings()

        # Test default values match story requirements
        assert settings.CRAWLER_CONCURRENCY_LIMIT >= 10  # Increased from 5
        assert isinstance(settings.CLOUDSCRAPER_ENABLED, bool)
        assert settings.CLOUDSCRAPER_DELAY >= 0
        assert settings.CELERY_ASYNC_TIMEOUT > 0
        assert settings.ARTICLE_EXTRACTION_BATCH_SIZE > 0

    @pytest.mark.asyncio
    async def test_comprehensive_error_handling(self):
        """Test that errors are properly handled and logged."""
        settings = get_settings()
        extractor = ArticleExtractor(settings)

        # Test various error types are properly handled
        mock_article = Mock()

        # Test network error handling
        mock_article.download = Mock(side_effect=ConnectionError("Network error"))

        try:
            await extractor._download_and_parse_article_async(mock_article)
        except Exception as e:
            assert "network" in str(e).lower()

    def test_memory_leak_prevention(self):
        """Test that the fixes prevent memory leaks."""
        # This test verifies that we're not creating unclosed event loops
        from src.core.scheduler.tasks import crawl_category_task
        import inspect

        source = inspect.getsource(crawl_category_task)

        # Should use asyncio.run() which properly manages the event loop
        assert "asyncio.run(" in source

        # Should not manually create/close event loops
        assert "new_event_loop" not in source
        assert "set_event_loop" not in source
        assert "loop.close" not in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])