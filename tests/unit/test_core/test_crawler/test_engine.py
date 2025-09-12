"""Unit tests for CrawlerEngine class.

This module contains comprehensive unit tests for the CrawlerEngine class,
covering all major functionality including Google News search, article extraction,
deduplication, and database operations.

Test Coverage:
- CrawlerEngine initialization and configuration validation
- Google News search with keyword OR logic and exclusions
- Article extraction batch processing
- Deduplication logic using URL hashes
- Category association and database persistence
- Error handling and retry logic
- Logging and correlation ID tracking

The tests use mocking to isolate the CrawlerEngine from external dependencies
like GoogleNewsSource, ArticleExtractor, and database repositories.
"""

import asyncio
import logging
import pytest
from typing import Dict, Any, List
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Test imports
from src.core.crawler.engine import CrawlerEngine, CrawlerError, GoogleNewsSearchError
from src.shared.config import Settings
from src.shared.exceptions import ConfigurationError


class TestCrawlerEngineInitialization:
    """Test CrawlerEngine initialization and configuration."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock(spec=Settings)
        settings.EXTRACTION_TIMEOUT = 30
        settings.EXTRACTION_MAX_RETRIES = 3
        settings.EXTRACTION_RETRY_BASE_DELAY = 1.0
        settings.EXTRACTION_RETRY_MULTIPLIER = 2.0
        return settings
    
    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing."""
        return Mock(spec=logging.Logger)
    
    @pytest.fixture
    def mock_article_extractor(self):
        """Create mock ArticleExtractor for testing."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_article_repo(self):
        """Create mock ArticleRepository for testing."""
        return AsyncMock()
    
    @patch('src.core.crawler.engine.GoogleNewsSource')
    def test_successful_initialization(
        self, 
        mock_google_news_source,
        mock_settings,
        mock_logger,
        mock_article_extractor,
        mock_article_repo
    ):
        """Test successful CrawlerEngine initialization."""
        # Arrange
        mock_google_news_instance = Mock()
        mock_google_news_source.return_value = mock_google_news_instance
        
        # Act
        crawler = CrawlerEngine(
            settings=mock_settings,
            logger=mock_logger,
            article_extractor=mock_article_extractor,
            article_repo=mock_article_repo
        )
        
        # Assert
        assert crawler.settings == mock_settings
        assert crawler.logger == mock_logger
        assert crawler.article_extractor == mock_article_extractor
        assert crawler.article_repo == mock_article_repo
        assert crawler.google_news == mock_google_news_instance
        mock_google_news_source.assert_called_once()
    
    @patch('src.core.crawler.engine.GoogleNewsSource', None)
    def test_initialization_fails_without_google_news(
        self,
        mock_settings,
        mock_logger,
        mock_article_extractor,
        mock_article_repo
    ):
        """Test CrawlerEngine initialization fails when GoogleNewsSource is unavailable."""
        # Act & Assert
        with pytest.raises(ConfigurationError, match="GoogleNewsSource not available"):
            CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    def test_initialization_validates_configuration(
        self,
        mock_logger,
        mock_article_extractor,
        mock_article_repo
    ):
        """Test CrawlerEngine validates configuration during initialization."""
        # Arrange - Invalid settings
        invalid_settings = Mock(spec=Settings)
        invalid_settings.EXTRACTION_TIMEOUT = 0  # Invalid timeout
        
        # Act & Assert
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            with pytest.raises(ConfigurationError, match="EXTRACTION_TIMEOUT must be positive"):
                CrawlerEngine(
                    settings=invalid_settings,
                    logger=mock_logger,
                    article_extractor=mock_article_extractor,
                    article_repo=mock_article_repo
                )


class TestGoogleNewsSearch:
    """Test Google News search functionality."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    def test_build_search_query_single_keyword(self, crawler_engine):
        """Test building search query with single keyword."""
        # Arrange
        keywords = ["python"]
        exclude_keywords = []
        
        # Act
        query = crawler_engine._build_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '"python"'
    
    def test_build_search_query_multiple_keywords(self, crawler_engine):
        """Test building search query with multiple keywords (OR logic)."""
        # Arrange
        keywords = ["python", "javascript", "AI"]
        exclude_keywords = []
        
        # Act
        query = crawler_engine._build_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '("python" OR "javascript" OR "AI")'
    
    def test_build_search_query_with_exclusions(self, crawler_engine):
        """Test building search query with exclude keywords."""
        # Arrange
        keywords = ["python", "programming"]
        exclude_keywords = ["java", "php"]
        
        # Act
        query = crawler_engine._build_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '("python" OR "programming") -"java" -"php"'
    
    def test_build_search_query_empty_keywords(self, crawler_engine):
        """Test building search query with empty keywords list."""
        # Arrange
        keywords = []
        exclude_keywords = []
        
        # Act
        query = crawler_engine._build_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == ""
    
    @pytest.mark.asyncio
    async def test_search_google_news_success(self, crawler_engine):
        """Test successful Google News search."""
        # Arrange
        keywords = ["technology", "AI"]
        exclude_keywords = ["java"]
        correlation_id = str(uuid4())
        
        # Mock search results
        mock_entry1 = Mock()
        mock_entry1.link = "https://example.com/article1"
        mock_entry2 = Mock()
        mock_entry2.link = "https://example.com/article2"
        
        mock_results = Mock()
        mock_results.entries = [mock_entry1, mock_entry2]
        
        # Mock google_news.search to return mock results
        with patch.object(crawler_engine.google_news, 'search', return_value=mock_results) as mock_search:
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_executor = Mock()
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_results)
                
                # Act
                urls = await crawler_engine.search_google_news(
                    keywords=keywords, 
                    exclude_keywords=exclude_keywords, 
                    correlation_id=correlation_id
                )
                
                # Assert
                assert len(urls) == 2
                assert "https://example.com/article1" in urls
                assert "https://example.com/article2" in urls
    
    @pytest.mark.asyncio
    async def test_search_google_news_empty_keywords(self, crawler_engine):
        """Test Google News search with empty keywords raises error."""
        # Arrange
        keywords = []
        correlation_id = str(uuid4())
        
        # Act & Assert
        with pytest.raises(GoogleNewsSearchError, match="Keywords list cannot be empty"):
            await crawler_engine.search_google_news(keywords=keywords, correlation_id=correlation_id)
    
    @pytest.mark.asyncio
    async def test_search_google_news_handles_exceptions(self, crawler_engine):
        """Test Google News search handles exceptions properly."""
        # Arrange
        keywords = ["technology"]
        correlation_id = str(uuid4())
        
        # Mock google_news.search to raise exception
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Network error"))
            
            # Act & Assert
            with pytest.raises(GoogleNewsSearchError, match="Failed to search Google News"):
                await crawler_engine.search_google_news(keywords=keywords, correlation_id=correlation_id)


class TestArticleExtraction:
    """Test article extraction functionality."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_extract_articles_batch_success(self, crawler_engine):
        """Test successful batch article extraction."""
        # Arrange
        urls = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://example.com/article3"
        ]
        correlation_id = str(uuid4())
        
        # Mock extraction results
        mock_article1 = {
            "title": "Article 1",
            "content": "Content 1",
            "source_url": urls[0],
            "url_hash": "hash1"
        }
        mock_article2 = {
            "title": "Article 2",
            "content": "Content 2",
            "source_url": urls[1],
            "url_hash": "hash2"
        }
        
        # Mock ArticleExtractor to return successful extractions
        crawler_engine.article_extractor.extract_article_metadata = AsyncMock()
        crawler_engine.article_extractor.extract_article_metadata.side_effect = [
            mock_article1,
            mock_article2,
            None  # Third extraction fails
        ]
        
        # Act
        results = await crawler_engine.extract_articles_batch(urls, correlation_id)
        
        # Assert
        assert len(results) == 2
        assert results[0] == mock_article1
        assert results[1] == mock_article2
        assert crawler_engine.article_extractor.extract_article_metadata.call_count == 3
    
    @pytest.mark.asyncio
    async def test_extract_articles_batch_empty_urls(self, crawler_engine):
        """Test batch extraction with empty URLs list."""
        # Arrange
        urls = []
        correlation_id = str(uuid4())
        
        # Act
        results = await crawler_engine.extract_articles_batch(urls, correlation_id)
        
        # Assert
        assert results == []
        crawler_engine.article_extractor.extract_article_metadata.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_extract_articles_batch_handles_exceptions(self, crawler_engine):
        """Test batch extraction handles extraction exceptions properly."""
        # Arrange
        urls = ["https://example.com/article1", "https://example.com/article2"]
        correlation_id = str(uuid4())
        
        # Mock ArticleExtractor to raise exceptions
        crawler_engine.article_extractor.extract_article_metadata = AsyncMock()
        crawler_engine.article_extractor.extract_article_metadata.side_effect = [
            {"title": "Article 1", "url_hash": "hash1"},  # Success
            Exception("Extraction failed")  # Exception
        ]
        
        # Act
        results = await crawler_engine.extract_articles_batch(urls, correlation_id)
        
        # Assert
        assert len(results) == 1  # Only successful extraction
        assert results[0]["title"] == "Article 1"


class TestDeduplicationAndPersistence:
    """Test deduplication and database persistence functionality."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_save_articles_with_deduplication_new_articles(self, crawler_engine):
        """Test saving new articles (no duplicates)."""
        # Arrange
        category_id = uuid4()
        correlation_id = str(uuid4())
        articles = [
            {
                "title": "Article 1",
                "content": "Content 1",
                "source_url": "https://example.com/1",
                "url_hash": "hash1"
            },
            {
                "title": "Article 2",
                "content": "Content 2",
                "source_url": "https://example.com/2",
                "url_hash": "hash2"
            }
        ]
        
        # Mock repository methods
        crawler_engine.article_repo.get_by_url_hash = AsyncMock(return_value=None)  # No existing articles
        crawler_engine.article_repo.create_with_category = AsyncMock()
        mock_new_article1 = Mock()
        mock_new_article1.id = uuid4()
        mock_new_article2 = Mock()
        mock_new_article2.id = uuid4()
        crawler_engine.article_repo.create_with_category.side_effect = [mock_new_article1, mock_new_article2]
        
        # Act
        saved_count = await crawler_engine.save_articles_with_deduplication(
            articles, category_id, correlation_id
        )
        
        # Assert
        assert saved_count == 2
        assert crawler_engine.article_repo.get_by_url_hash.call_count == 2
        assert crawler_engine.article_repo.create_with_category.call_count == 2
    
    @pytest.mark.asyncio
    async def test_save_articles_with_deduplication_existing_articles(self, crawler_engine):
        """Test handling of duplicate articles (existing URL hashes)."""
        # Arrange
        category_id = uuid4()
        correlation_id = str(uuid4())
        articles = [
            {
                "title": "Article 1",
                "content": "Content 1",
                "source_url": "https://example.com/1",
                "url_hash": "hash1"
            }
        ]
        
        # Mock existing article
        existing_article = Mock()
        existing_article.id = uuid4()
        
        # Mock repository methods
        crawler_engine.article_repo.get_by_url_hash = AsyncMock(return_value=existing_article)
        crawler_engine.article_repo.update_last_seen = AsyncMock()
        crawler_engine.article_repo.ensure_category_association = AsyncMock()
        
        # Act
        saved_count = await crawler_engine.save_articles_with_deduplication(
            articles, category_id, correlation_id
        )
        
        # Assert
        assert saved_count == 0  # No new articles saved
        crawler_engine.article_repo.update_last_seen.assert_called_once_with(existing_article.id)
        crawler_engine.article_repo.ensure_category_association.assert_called_once_with(
            existing_article.id, category_id
        )
    
    @pytest.mark.asyncio
    async def test_save_articles_with_deduplication_missing_url_hash(self, crawler_engine):
        """Test handling of articles without URL hash."""
        # Arrange
        category_id = uuid4()
        correlation_id = str(uuid4())
        articles = [
            {
                "title": "Article 1",
                "content": "Content 1",
                "source_url": "https://example.com/1"
                # Missing url_hash
            }
        ]
        
        # Act
        saved_count = await crawler_engine.save_articles_with_deduplication(
            articles, category_id, correlation_id
        )
        
        # Assert
        assert saved_count == 0
        crawler_engine.article_repo.get_by_url_hash.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_save_articles_with_deduplication_empty_list(self, crawler_engine):
        """Test saving empty articles list."""
        # Arrange
        category_id = uuid4()
        correlation_id = str(uuid4())
        articles = []
        
        # Act
        saved_count = await crawler_engine.save_articles_with_deduplication(
            articles, category_id, correlation_id
        )
        
        # Assert
        assert saved_count == 0


class TestCrawlCategory:
    """Test the main crawl_category method integration."""
    
    @pytest.fixture
    def mock_category(self):
        """Create mock category for testing."""
        category = Mock()
        category.id = uuid4()
        category.name = "Technology"
        category.keywords = ["python", "AI"]
        category.exclude_keywords = ["java"]
        return category
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_crawl_category_success(self, crawler_engine, mock_category):
        """Test successful category crawling end-to-end."""
        # Arrange
        mock_urls = ["https://example.com/1", "https://example.com/2"]
        mock_articles = [
            {"title": "Article 1", "url_hash": "hash1"},
            {"title": "Article 2", "url_hash": "hash2"}
        ]
        
        # Mock all the methods
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            with patch.object(crawler_engine, 'extract_articles_batch', new_callable=AsyncMock) as mock_extract:
                with patch.object(crawler_engine, 'save_articles_with_deduplication', new_callable=AsyncMock) as mock_save:
                    
                    mock_search.return_value = mock_urls
                    mock_extract.return_value = mock_articles
                    mock_save.return_value = 2
                    
                    # Act
                    result = await crawler_engine.crawl_category(mock_category)
                    
                    # Assert
                    assert result == mock_articles
                    mock_search.assert_called_once()
                    mock_extract.assert_called_once_with(
                        urls=mock_urls,
                        correlation_id=mock_search.call_args[1]['correlation_id']
                    )
                    mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawl_category_no_urls_found(self, crawler_engine, mock_category):
        """Test category crawling when no URLs are found."""
        # Arrange - Mock search returns empty list
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            
            # Act
            result = await crawler_engine.crawl_category(mock_category)
            
            # Assert
            assert result == []
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawl_category_extraction_fails(self, crawler_engine, mock_category):
        """Test category crawling when article extraction fails."""
        # Arrange
        mock_urls = ["https://example.com/1", "https://example.com/2"]
        
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            with patch.object(crawler_engine, 'extract_articles_batch', new_callable=AsyncMock) as mock_extract:
                
                mock_search.return_value = mock_urls
                mock_extract.return_value = []  # No successful extractions
                
                # Act
                result = await crawler_engine.crawl_category(mock_category)
                
                # Assert
                assert result == []
                mock_search.assert_called_once()
                mock_extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawl_category_handles_exceptions(self, crawler_engine, mock_category):
        """Test category crawling handles exceptions and raises CrawlerError."""
        # Arrange - Mock search to raise exception
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("Search failed")
            
            # Act & Assert
            with pytest.raises(CrawlerError, match="Failed to crawl category"):
                await crawler_engine.crawl_category(mock_category)


class TestLoggingAndCorrelationIds:
    """Test logging functionality and correlation ID tracking."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_search_logs_correlation_id(self, crawler_engine):
        """Test that search operations log correlation IDs properly."""
        # Arrange
        keywords = ["technology"]
        correlation_id = "test-correlation-id"
        
        # Mock google news search
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=[])
            
            # Act
            await crawler_engine.search_google_news(keywords=keywords, correlation_id=correlation_id)
            
            # Assert - Check that logger.info was called with correlation_id
            info_calls = [call for call in crawler_engine.logger.info.call_args_list 
                         if 'correlation_id' in str(call)]
            assert len(info_calls) > 0
            
            # Verify correlation_id is included in logging extra data
            found_correlation = False
            for call in info_calls:
                args, kwargs = call
                if 'extra' in kwargs:
                    extra = kwargs['extra']
                    if 'correlation_id' in extra and extra['correlation_id'] == correlation_id:
                        found_correlation = True
                        break
            assert found_correlation, "correlation_id not found in logging extra data"


# Fixtures for all tests
@pytest.fixture
def mock_settings():
    """Create mock settings for all tests."""
    settings = Mock(spec=Settings)
    settings.EXTRACTION_TIMEOUT = 30
    settings.EXTRACTION_MAX_RETRIES = 3
    settings.EXTRACTION_RETRY_BASE_DELAY = 1.0
    settings.EXTRACTION_RETRY_MULTIPLIER = 2.0
    return settings


@pytest.fixture
def mock_logger():
    """Create mock logger for all tests."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_article_extractor():
    """Create mock ArticleExtractor for all tests."""
    return AsyncMock()


@pytest.fixture
def mock_article_repo():
    """Create mock ArticleRepository for all tests."""
    return AsyncMock()


class TestEnhancedMultiKeywordSearch:
    """Test enhanced multi-keyword OR search functionality."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    def test_build_advanced_search_query_single_keyword(self, crawler_engine):
        """Test advanced search query building with single keyword."""
        # Arrange
        keywords = ["machine learning"]
        exclude_keywords = []
        
        # Act
        query = crawler_engine._build_advanced_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '"machine learning"'
    
    def test_build_advanced_search_query_multiple_keywords(self, crawler_engine):
        """Test advanced search query building with multiple keywords."""
        # Arrange
        keywords = ["python", "javascript", "AI", "machine learning"]
        exclude_keywords = []
        
        # Act
        query = crawler_engine._build_advanced_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '("python" OR "javascript" OR "AI" OR "machine learning")'
    
    def test_build_advanced_search_query_with_exclusions(self, crawler_engine):
        """Test advanced search query building with exclude keywords."""
        # Arrange
        keywords = ["AI", "machine learning", "deep learning"]
        exclude_keywords = ["cryptocurrency", "bitcoin"]
        
        # Act
        query = crawler_engine._build_advanced_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '("AI" OR "machine learning" OR "deep learning") -"cryptocurrency" -"bitcoin"'
    
    def test_build_advanced_search_query_with_special_characters(self, crawler_engine):
        """Test advanced search query building handles special characters."""
        # Arrange
        keywords = ["C++", "Node.js", "ASP.NET"]
        exclude_keywords = ["SQL*Plus"]
        
        # Act
        query = crawler_engine._build_advanced_search_query(keywords, exclude_keywords)
        
        # Assert
        assert query == '("C" OR "Node.js" OR "ASP.NET") -"SQLPlus"'
    
    def test_sanitize_keywords_removes_duplicates(self, crawler_engine):
        """Test keyword sanitization removes duplicates."""
        # Arrange
        keywords = ["python", "Python", "PYTHON", "javascript"]
        
        # Act
        cleaned = crawler_engine._sanitize_keywords(keywords)
        
        # Assert
        assert len(cleaned) == 2  # python (deduplicated) + javascript
        assert "python" in cleaned
        assert "javascript" in cleaned
    
    def test_sanitize_keywords_handles_long_keywords(self, crawler_engine):
        """Test keyword sanitization handles overly long keywords."""
        # Arrange
        long_keyword = "a" * 150  # Exceeds max length
        keywords = ["python", long_keyword, "javascript"]
        
        # Act
        cleaned = crawler_engine._sanitize_keywords(keywords)
        
        # Assert
        assert len(cleaned) == 2  # long keyword should be filtered out
        assert "python" in cleaned
        assert "javascript" in cleaned
        assert long_keyword not in cleaned
    
    def test_classify_query_complexity(self, crawler_engine):
        """Test query complexity classification."""
        # Test simple query
        simple = crawler_engine._classify_query_complexity(["python"], [])
        assert simple == "simple"
        
        # Test medium query
        medium = crawler_engine._classify_query_complexity(["python", "javascript"], ["java"])
        assert medium == "medium"
        
        # Test complex query
        complex_keywords = ["python", "javascript", "go", "rust", "java", "c++"]
        complex_query = crawler_engine._classify_query_complexity(complex_keywords, ["php"])
        assert complex_query == "complex"
    
    def test_get_rate_limit_delay(self, crawler_engine):
        """Test rate limiting delay calculation."""
        # Test different complexity levels
        simple_delay = crawler_engine._get_rate_limit_delay("simple")
        assert simple_delay == 1.0
        
        medium_delay = crawler_engine._get_rate_limit_delay("medium")
        assert medium_delay == 1.5
        
        complex_delay = crawler_engine._get_rate_limit_delay("complex")
        assert complex_delay == 2.0
        
        # Test unknown complexity defaults to complex
        unknown_delay = crawler_engine._get_rate_limit_delay("unknown")
        assert unknown_delay == 2.0
    
    @pytest.mark.asyncio
    async def test_search_google_news_multi_keyword_success(self, crawler_engine):
        """Test successful multi-keyword search."""
        # Arrange
        keywords = ["python", "javascript", "AI"]
        exclude_keywords = ["java"]
        max_results = 50
        
        # Mock search_google_news method
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            expected_urls = ["https://example.com/1", "https://example.com/2"]
            mock_search.return_value = expected_urls
            
            # Act
            urls = await crawler_engine.search_google_news_multi_keyword(
                keywords=keywords,
                exclude_keywords=exclude_keywords,
                max_results=max_results
            )
            
            # Assert
            assert urls == expected_urls
            mock_search.assert_called_once()
            call_args = mock_search.call_args
            assert call_args[1]['keywords'] == keywords
            assert call_args[1]['exclude_keywords'] == exclude_keywords
            assert call_args[1]['max_results'] == max_results
    
    @pytest.mark.asyncio
    async def test_search_google_news_multi_keyword_empty_keywords(self, crawler_engine):
        """Test multi-keyword search with empty keywords raises error."""
        # Arrange
        keywords = []
        
        # Act & Assert
        with pytest.raises(GoogleNewsSearchError, match="Keywords list cannot be empty"):
            await crawler_engine.search_google_news_multi_keyword(keywords)


class TestPaginationHandling:
    """Test pagination handling functionality."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_search_google_news_with_pagination_success(self, crawler_engine):
        """Test successful paginated Google News search."""
        # Arrange
        keywords = ["technology", "AI"]
        max_results = 75
        page_size = 25
        max_pages = 3
        
        # Mock search_google_news to return different URLs for each page
        page_1_urls = [f"https://example.com/page1/{i}" for i in range(25)]
        page_2_urls = [f"https://example.com/page2/{i}" for i in range(25)]
        page_3_urls = [f"https://example.com/page3/{i}" for i in range(25)]
        
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = [page_1_urls, page_2_urls, page_3_urls]
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                # Act
                urls = await crawler_engine.search_google_news_with_pagination(
                    keywords=keywords,
                    max_results=max_results,
                    page_size=page_size,
                    max_pages=max_pages
                )
                
                # Assert
                assert len(urls) == 75  # All pages collected
                assert mock_search.call_count == 3
                assert mock_sleep.call_count == 2  # 2 delays between 3 pages
                
                # Verify all URLs are unique
                assert len(set(urls)) == 75
    
    @pytest.mark.asyncio
    async def test_search_google_news_with_pagination_early_termination(self, crawler_engine):
        """Test pagination stops when no new results are found."""
        # Arrange
        keywords = ["rare_keyword"]
        max_results = 100
        page_size = 25
        
        # Mock first page returns results, second page returns empty
        page_1_urls = [f"https://example.com/page1/{i}" for i in range(25)]
        
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = [page_1_urls, []]  # Second page is empty
            
            # Act
            urls = await crawler_engine.search_google_news_with_pagination(
                keywords=keywords,
                max_results=max_results,
                page_size=page_size
            )
            
            # Assert
            assert len(urls) == 25
            assert mock_search.call_count == 2  # Stopped after empty page
    
    @pytest.mark.asyncio
    async def test_search_google_news_with_pagination_duplicate_detection(self, crawler_engine):
        """Test pagination handles duplicate URLs across pages."""
        # Arrange
        keywords = ["technology"]
        max_results = 50
        page_size = 25
        
        # Mock pages with some overlapping URLs
        page_1_urls = [f"https://example.com/article_{i}" for i in range(25)]
        page_2_urls = [f"https://example.com/article_{i}" for i in range(20, 45)]  # 5 duplicates + 20 new
        
        with patch.object(crawler_engine, 'search_google_news', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = [page_1_urls, page_2_urls, []]  # Add empty third page
            
            # Act
            urls = await crawler_engine.search_google_news_with_pagination(
                keywords=keywords,
                max_results=max_results,
                page_size=page_size
            )
            
            # Assert
            assert len(urls) == 45  # 25 + 20 unique URLs
            assert len(set(urls)) == 45  # Verify all are unique
    
    @pytest.mark.asyncio
    async def test_pagination_error_handling(self, crawler_engine):
        """Test pagination error handling with retry logic."""
        # Arrange
        search_function = AsyncMock()
        search_function.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            ["https://example.com/success"]
        ]
        
        # Act
        result = await crawler_engine.handle_pagination_errors(
            search_function=search_function,
            max_retries=3
        )
        
        # Assert
        assert result == ["https://example.com/success"]
        assert search_function.call_count == 3
    
    @pytest.mark.asyncio
    async def test_pagination_error_handling_all_failures(self, crawler_engine):
        """Test pagination error handling when all attempts fail."""
        # Arrange
        search_function = AsyncMock()
        search_function.side_effect = Exception("Persistent error")
        
        # Act
        result = await crawler_engine.handle_pagination_errors(
            search_function=search_function,
            max_retries=2
        )
        
        # Assert
        assert result == []  # Returns empty list on complete failure
        assert search_function.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_get_pagination_metrics(self, crawler_engine):
        """Test pagination performance metrics calculation."""
        # Arrange
        total_results = 150
        page_size = 25
        
        # Act
        metrics = await crawler_engine.get_pagination_metrics(total_results, page_size)
        
        # Assert
        assert metrics["total_results"] == 150
        assert metrics["page_size"] == 25
        assert metrics["estimated_pages"] == 6  # ceil(150/25)
        assert metrics["efficiency_score"] == 25.0  # 150/6 pages
        assert metrics["recommended_page_size"] == 50  # For 150 results


class TestEnhancedDeduplication:
    """Test enhanced deduplication mechanism."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.mark.asyncio
    async def test_save_articles_with_advanced_deduplication_success(self, crawler_engine):
        """Test successful advanced deduplication."""
        # Arrange
        articles = [
            {
                "title": "AI Article 1",
                "content": "Content about AI",
                "source_url": "https://example.com/1",
                "relevance_score": 0.8
            },
            {
                "title": "Tech Article 2",
                "content": "Technology content",
                "source_url": "https://example.com/2", 
                "relevance_score": 0.6
            }
        ]
        category_id = uuid4()
        keywords_matched = ["AI", "technology"]
        search_query_used = '("AI" OR "technology")'
        
        # Mock repository method
        crawler_engine.article_repo.bulk_create_with_enhanced_deduplication = AsyncMock()
        crawler_engine.article_repo.bulk_create_with_enhanced_deduplication.return_value = (2, 0, 0)  # 2 new, 0 updated, 0 skipped
        
        # Act
        result = await crawler_engine.save_articles_with_advanced_deduplication(
            articles=articles,
            category_id=category_id,
            keywords_matched=keywords_matched,
            search_query_used=search_query_used
        )
        
        # Assert
        assert result == 2
        crawler_engine.article_repo.bulk_create_with_enhanced_deduplication.assert_called_once()
        call_args = crawler_engine.article_repo.bulk_create_with_enhanced_deduplication.call_args
        assert call_args[1]['category_id'] == category_id
        assert call_args[1]['keyword_matched'] == "AI, technology"
        assert call_args[1]['search_query_used'] == search_query_used
    
    @pytest.mark.asyncio
    async def test_save_articles_with_advanced_deduplication_fallback(self, crawler_engine):
        """Test fallback to basic deduplication when advanced fails."""
        # Arrange
        articles = [{"title": "Test", "source_url": "https://example.com"}]
        category_id = uuid4()
        
        # Mock repository method to fail
        crawler_engine.article_repo.bulk_create_with_enhanced_deduplication = AsyncMock()
        crawler_engine.article_repo.bulk_create_with_enhanced_deduplication.side_effect = Exception("DB Error")
        
        # Mock fallback method
        with patch.object(crawler_engine, 'save_articles_with_deduplication', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = 1
            
            # Act
            result = await crawler_engine.save_articles_with_advanced_deduplication(
                articles=articles,
                category_id=category_id,
                keywords_matched=["test"],
                search_query_used="test"
            )
            
            # Assert
            assert result == 1
            mock_fallback.assert_called_once()


class TestCategoryAssociationLogic:
    """Test improved category association logic."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        mock_settings.CATEGORY_RELEVANCE_THRESHOLD = 0.3
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    def test_calculate_category_relevance_high_score(self, crawler_engine):
        """Test relevance calculation for highly relevant article."""
        # Arrange
        article = {
            "title": "Python Machine Learning Tutorial",
            "content": "This article covers Python programming for machine learning applications..."
        }
        
        category = Mock()
        category.keywords = ["python", "machine learning"]
        category.exclude_keywords = []
        
        # Act
        relevance = crawler_engine.calculate_category_relevance(article, category)
        
        # Assert
        assert relevance > 0.5  # Should be high relevance
    
    def test_calculate_category_relevance_with_exclusions(self, crawler_engine):
        """Test relevance calculation with exclude keywords penalty."""
        # Arrange
        article = {
            "title": "Python and Java Programming Comparison",
            "content": "This article compares Python and Java programming languages..."
        }
        
        category = Mock()
        category.keywords = ["python", "programming"]
        category.exclude_keywords = ["java"]  # Should reduce relevance
        
        # Act
        relevance = crawler_engine.calculate_category_relevance(article, category)
        
        # Assert
        assert relevance < 1.0  # Should be reduced due to exclude keyword
        # The exact reduction depends on the penalty calculation, but should be less than perfect score
    
    def test_calculate_category_relevance_no_match(self, crawler_engine):
        """Test relevance calculation for non-matching article."""
        # Arrange
        article = {
            "title": "Cooking Recipes",
            "content": "This article is about cooking and recipes..."
        }
        
        category = Mock()
        category.keywords = ["python", "programming"]
        category.exclude_keywords = []
        
        # Act
        relevance = crawler_engine.calculate_category_relevance(article, category)
        
        # Assert
        assert relevance == 0.0
    
    def test_calculate_category_relevance_title_vs_content_weighting(self, crawler_engine):
        """Test that title matches are weighted higher than content matches."""
        # Arrange
        title_match_article = {
            "title": "Python Programming Guide",
            "content": "General programming content here..."
        }
        
        content_match_article = {
            "title": "General Programming Guide", 
            "content": "This content focuses on Python programming..."
        }
        
        category = Mock()
        category.keywords = ["python"]
        category.exclude_keywords = []
        
        # Act
        title_relevance = crawler_engine.calculate_category_relevance(title_match_article, category)
        content_relevance = crawler_engine.calculate_category_relevance(content_match_article, category)
        
        # Assert
        assert title_relevance > content_relevance
    
    @pytest.mark.asyncio
    async def test_associate_articles_with_multiple_categories(self, crawler_engine):
        """Test associating articles with multiple matching categories."""
        # Arrange
        articles = [
            {
                "title": "Python Machine Learning Tutorial",
                "content": "Python ML content...",
                "source_url": "https://example.com/1"
            }
        ]
        
        # Create mock categories
        python_category = Mock()
        python_category.id = uuid4()
        python_category.name = "Python"
        python_category.keywords = ["python"]
        python_category.exclude_keywords = []
        
        ml_category = Mock()
        ml_category.id = uuid4()
        ml_category.name = "Machine Learning"
        ml_category.keywords = ["machine learning", "ML"]
        ml_category.exclude_keywords = []
        
        categories = [python_category, ml_category]
        
        # Mock the association creation
        with patch.object(crawler_engine, '_create_category_association_with_metadata', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = True
            
            # Act
            stats = await crawler_engine.associate_articles_with_multiple_categories(
                articles=articles,
                categories=categories
            )
            
            # Assert
            assert stats["articles_processed"] == 1
            assert stats["associations_created"] >= 1  # Should match at least one category
            assert mock_create.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_validate_category_associations(self, crawler_engine):
        """Test category association validation."""
        # Arrange
        article = {"title": "Test Article", "source_url": "https://example.com"}
        category_associations = [
            {"category_name": "Python", "relevance_score": 0.8},
            {"category_name": "AI", "relevance_score": 0.6},
            {"category_name": "General", "relevance_score": 0.2}
        ]
        
        # Act
        validation = await crawler_engine.validate_category_associations(
            article=article,
            category_associations=category_associations
        )
        
        # Assert
        assert validation["is_valid"] == True
        assert validation["association_count"] == 3
        assert validation["high_confidence_count"] == 1  # 0.8 score
        assert validation["medium_confidence_count"] == 1  # 0.6 score
        assert validation["low_confidence_count"] == 1  # 0.2 score
        assert len(validation["warnings"]) == 1  # Low relevance warning
    
    @pytest.mark.asyncio
    async def test_validate_category_associations_no_associations(self, crawler_engine):
        """Test validation when no category associations exist."""
        # Arrange
        article = {"title": "Test Article"}
        category_associations = []
        
        # Act
        validation = await crawler_engine.validate_category_associations(
            article=article,
            category_associations=category_associations
        )
        
        # Assert
        assert validation["is_valid"] == False
        assert "No category associations found for article" in validation["warnings"]


class TestAdvancedCrawlWorkflow:
    """Test the advanced category crawl workflow integration."""
    
    @pytest.fixture
    def crawler_engine(self, mock_settings, mock_logger, mock_article_extractor, mock_article_repo):
        """Create CrawlerEngine instance for testing."""
        mock_settings.MAX_RESULTS_PER_SEARCH = 200
        with patch('src.core.crawler.engine.GoogleNewsSource'):
            return CrawlerEngine(
                settings=mock_settings,
                logger=mock_logger,
                article_extractor=mock_article_extractor,
                article_repo=mock_article_repo
            )
    
    @pytest.fixture
    def mock_category(self):
        """Create mock category for advanced testing."""
        category = Mock()
        category.id = uuid4()
        category.name = "Advanced Technology"
        category.keywords = ["AI", "machine learning", "deep learning"]
        category.exclude_keywords = ["cryptocurrency"]
        return category
    
    @pytest.mark.asyncio
    async def test_crawl_category_advanced_success(self, crawler_engine, mock_category):
        """Test successful advanced category crawling with relevance scoring."""
        # Arrange
        mock_urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        mock_extracted_articles = [
            {"title": "AI Tutorial", "content": "Machine learning content", "source_url": mock_urls[0]},
            {"title": "Deep Learning Guide", "content": "AI and ML guide", "source_url": mock_urls[1]},
            {"title": "Tech News", "content": "General technology news", "source_url": mock_urls[2]}
        ]
        
        # Mock the methods used in advanced crawl
        with patch.object(crawler_engine, 'search_google_news_multi_keyword', new_callable=AsyncMock) as mock_search:
            with patch.object(crawler_engine, 'extract_articles_batch', new_callable=AsyncMock) as mock_extract:
                with patch.object(crawler_engine, 'save_articles_with_advanced_deduplication', new_callable=AsyncMock) as mock_save:
                    
                    mock_search.return_value = mock_urls
                    mock_extract.return_value = mock_extracted_articles
                    mock_save.return_value = 3
                    
                    # Act
                    result = await crawler_engine.crawl_category_advanced(mock_category)
                    
                    # Assert
                    assert len(result) == 3
                    
                    # Verify relevance scores were added
                    for article in result:
                        assert 'relevance_score' in article
                        assert 0.0 <= article['relevance_score'] <= 1.0
                    
                    # Verify all methods were called
                    mock_search.assert_called_once()
                    mock_extract.assert_called_once()
                    mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crawl_category_advanced_no_results(self, crawler_engine, mock_category):
        """Test advanced crawl when no articles are found."""
        # Arrange
        with patch.object(crawler_engine, 'search_google_news_multi_keyword', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            
            # Act
            result = await crawler_engine.crawl_category_advanced(mock_category)
            
            # Assert
            assert result == []
            mock_search.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_advanced_crawl_relevance_scoring_integration(self, crawler_engine, mock_category):
        """Test that advanced crawl properly integrates relevance scoring."""
        # Arrange
        mock_urls = ["https://example.com/1"]
        mock_article = {
            "title": "Machine Learning with AI",
            "content": "Deep learning and artificial intelligence tutorial",
            "source_url": mock_urls[0]
        }
        
        with patch.object(crawler_engine, 'search_google_news_multi_keyword', new_callable=AsyncMock) as mock_search:
            with patch.object(crawler_engine, 'extract_articles_batch', new_callable=AsyncMock) as mock_extract:
                with patch.object(crawler_engine, 'save_articles_with_advanced_deduplication', new_callable=AsyncMock) as mock_save:
                    
                    mock_search.return_value = mock_urls
                    mock_extract.return_value = [mock_article]
                    mock_save.return_value = 1
                    
                    # Act
                    result = await crawler_engine.crawl_category_advanced(mock_category)
                    
                    # Assert
                    assert len(result) == 1
                    scored_article = result[0]
                    
                    # Should have high relevance score due to matching keywords
                    assert scored_article['relevance_score'] > 0.7
                    
                    # Verify the article contains the expected fields
                    assert 'title' in scored_article
                    assert 'content' in scored_article
                    assert 'source_url' in scored_article