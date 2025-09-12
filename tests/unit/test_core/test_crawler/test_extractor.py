"""Unit tests for ArticleExtractor module."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from src.core.crawler.extractor import ArticleExtractor
from src.shared.config import Settings
from src.shared.exceptions import (
    ExtractionError,
    ExtractionTimeoutError,
    ExtractionParsingError,
    ExtractionNetworkError
)


class TestArticleExtractor:
    """Test cases for ArticleExtractor class."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing."""
        return Mock()
    
    @pytest.fixture
    def test_settings(self):
        """Create test settings with realistic values."""
        settings = Mock(spec=Settings)
        settings.EXTRACTION_TIMEOUT = 30
        settings.EXTRACTION_MAX_RETRIES = 3
        settings.EXTRACTION_RETRY_BASE_DELAY = 1.0
        settings.EXTRACTION_RETRY_MULTIPLIER = 2.0
        settings.NEWSPAPER_LANGUAGE = "en"
        settings.NEWSPAPER_KEEP_ARTICLE_HTML = True
        settings.NEWSPAPER_FETCH_IMAGES = True
        settings.NEWSPAPER_HTTP_SUCCESS_ONLY = True
        return settings
    
    @pytest.fixture
    def extractor(self, test_settings, mock_logger):
        """Create ArticleExtractor instance for testing."""
        return ArticleExtractor(settings=test_settings, logger=mock_logger)
    
    @pytest.fixture
    def mock_article(self):
        """Create mock newspaper Article with sample data."""
        article = Mock()
        article.title = "Test Article Title"
        article.text = "This is a sample article content with more than fifty characters to meet minimum length requirements."
        article.authors = ["John Doe", "Jane Smith"]
        article.publish_date = datetime(2023, 10, 15, 14, 30, 0)
        article.top_image = "https://example.com/image.jpg"
        article.meta_data = {"title": "Meta Title"}
        return article
    
    def test_extractor_initialization(self, test_settings, mock_logger):
        """Test ArticleExtractor initialization and configuration."""
        extractor = ArticleExtractor(settings=test_settings, logger=mock_logger)
        
        assert extractor.settings == test_settings
        assert extractor.logger == mock_logger
        assert extractor.config is not None
        assert extractor.config.language == "en"
        assert extractor.config.keep_article_html is True
        assert extractor.config.fetch_images is True
        assert extractor.config.http_success_only is True
        assert extractor.config.memoize_articles is False
        assert extractor.config.request_timeout == 30
        assert extractor.config.number_threads == 1
    
    def test_extractor_initialization_with_default_logger(self, test_settings):
        """Test ArticleExtractor initialization with default logger."""
        extractor = ArticleExtractor(settings=test_settings)
        
        assert extractor.logger is not None
        assert extractor.logger.name == "src.core.crawler.extractor"
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_success(self, extractor, mock_article):
        """Test successful article extraction with all metadata fields."""
        test_url = "https://example.com/article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock()
            mock_instance.parse = Mock()
            
            # Configure mock article with all fields
            mock_instance.title = mock_article.title
            mock_instance.text = mock_article.text
            mock_instance.authors = mock_article.authors
            mock_instance.publish_date = mock_article.publish_date
            mock_instance.top_image = mock_article.top_image
            mock_instance.meta_data = mock_article.meta_data
            
            result = await extractor.extract_article_metadata(test_url)
        
        assert result is not None
        assert result["title"] == "Test Article Title"
        assert result["content"].startswith("This is a sample article content")
        assert result["author"] == "John Doe, Jane Smith"
        assert result["publish_date"] == datetime(2023, 10, 15, 14, 30, 0)
        assert result["image_url"] == "https://example.com/image.jpg"
        assert result["source_url"] == test_url
        assert result["url_hash"] is not None
        assert result["content_hash"] is not None
        assert result["extracted_at"] is not None
        
        # Verify logging
        extractor.logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_with_missing_optional_fields(self, extractor):
        """Test extraction with missing optional fields (author, publish_date, image_url)."""
        test_url = "https://example.com/article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock()
            mock_instance.parse = Mock()
            
            # Configure with only required fields
            mock_instance.title = "Test Article Title"
            mock_instance.text = "This is a sample article content with more than fifty characters to meet requirements."
            mock_instance.authors = []
            mock_instance.publish_date = None
            mock_instance.top_image = ""
            mock_instance.meta_data = {}
            
            result = await extractor.extract_article_metadata(test_url)
        
        assert result is not None
        assert result["title"] == "Test Article Title"
        assert result["content"] is not None
        assert result["author"] is None
        assert result["publish_date"] is None
        assert result["image_url"] is None
        assert result["source_url"] == test_url
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_with_empty_title_fails(self, extractor):
        """Test extraction failure when title is missing."""
        test_url = "https://example.com/article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock()
            mock_instance.parse = Mock()
            
            # Configure with no title
            mock_instance.title = ""
            mock_instance.text = "Some content"
            mock_instance.authors = []
            mock_instance.publish_date = None
            mock_instance.top_image = ""
            mock_instance.meta_data = {}
            
            result = await extractor.extract_article_metadata(test_url)
        
        # Should return None due to missing title
        assert result is None
        extractor.logger.error.assert_called()
    
    @pytest.mark.asyncio 
    async def test_extract_article_metadata_timeout_scenario(self, extractor):
        """Test timeout scenario with asyncio.timeout."""
        test_url = "https://example.com/slow-article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            
            # Simulate timeout during download
            async def slow_download():
                await asyncio.sleep(35)  # Longer than timeout
                
            mock_instance.download = Mock(side_effect=lambda: asyncio.run(slow_download()))
            
            with patch('asyncio.timeout', side_effect=asyncio.TimeoutError):
                result = await extractor.extract_article_metadata(test_url)
        
        assert result is None
        extractor.logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_network_error_with_retry(self, extractor):
        """Test network error handling with retry logic."""
        test_url = "https://example.com/network-error-article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            
            # First two calls fail with network error, third succeeds
            call_count = 0
            def mock_download():
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise Exception("Network connection failed")
                # Third call succeeds
                return None
            
            mock_instance.download = Mock(side_effect=mock_download)
            mock_instance.parse = Mock()
            
            # Configure successful response on third try
            mock_instance.title = "Success on Retry"
            mock_instance.text = "Content retrieved after network retry with sufficient length for validation."
            mock_instance.authors = []
            mock_instance.publish_date = None
            mock_instance.top_image = ""
            mock_instance.meta_data = {}
            
            result = await extractor.extract_article_metadata(test_url)
        
        assert result is not None
        assert result["title"] == "Success on Retry"
        assert call_count == 3  # Verify retry happened
        extractor.logger.warning.assert_called()  # Should log retry attempts
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_parsing_error_no_retry(self, extractor):
        """Test parsing error handling (should not retry)."""
        test_url = "https://example.com/parsing-error-article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock()
            mock_instance.parse = Mock(side_effect=Exception("Invalid HTML structure"))
            
            result = await extractor.extract_article_metadata(test_url)
        
        assert result is None
        extractor.logger.error.assert_called()
        # Verify no retry warning (parsing errors shouldn't retry)
        extractor.logger.warning.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff_timing(self, extractor):
        """Test retry logic with proper exponential backoff timing."""
        test_url = "https://example.com/retry-timing-test"
        
        with patch('asyncio.sleep') as mock_sleep:
            with patch('src.core.crawler.extractor.Article') as MockArticle:
                mock_instance = MockArticle.return_value
                
                # Always fail with network error to test all retry attempts
                mock_instance.download = Mock(side_effect=Exception("Network connection failed"))
                
                result = await extractor.extract_article_metadata(test_url)
        
        assert result is None
        
        # Verify exponential backoff timing: 1s, 2s, 4s
        expected_delays = [1.0, 2.0, 4.0]
        actual_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_calls == expected_delays
    
    @pytest.mark.asyncio
    async def test_extract_article_metadata_malformed_content_scenarios(self, extractor):
        """Test malformed content scenarios (empty content, invalid dates)."""
        test_url = "https://example.com/malformed-article"
        
        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock()
            mock_instance.parse = Mock()
            
            # Configure with malformed data
            mock_instance.title = "Valid Title"
            mock_instance.text = ""  # Empty content
            mock_instance.authors = []
            mock_instance.publish_date = "invalid-date-string"
            mock_instance.top_image = "not-a-url"
            mock_instance.meta_data = {}
            
            # Mock the executor calls to avoid issues with threading
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_event_loop = Mock()
                mock_loop.return_value = mock_event_loop
                
                # Make run_in_executor just call the function directly
                def run_directly(executor, func):
                    return func()
                
                mock_event_loop.run_in_executor = Mock(side_effect=run_directly)
                
                result = await extractor.extract_article_metadata(test_url)
        
        assert result is not None
        assert result["title"] == "Valid Title"
        assert result["content"] is None  # Empty content should be None
        assert result["publish_date"] is None  # Invalid date should be None
        assert result["image_url"] is None  # Invalid URL should be None
    
    @pytest.mark.asyncio
    async def test_configuration_integration_with_different_timeout_values(self, mock_logger):
        """Test configuration integration with different timeout values."""
        # Create settings with custom timeout
        custom_settings = Mock(spec=Settings)
        custom_settings.EXTRACTION_TIMEOUT = 60
        custom_settings.EXTRACTION_MAX_RETRIES = 5
        custom_settings.EXTRACTION_RETRY_BASE_DELAY = 0.5
        custom_settings.EXTRACTION_RETRY_MULTIPLIER = 3.0
        custom_settings.NEWSPAPER_LANGUAGE = "es"
        custom_settings.NEWSPAPER_KEEP_ARTICLE_HTML = False
        custom_settings.NEWSPAPER_FETCH_IMAGES = False
        custom_settings.NEWSPAPER_HTTP_SUCCESS_ONLY = False
        
        extractor = ArticleExtractor(settings=custom_settings, logger=mock_logger)
        
        # Verify configuration applied correctly
        assert extractor.config.request_timeout == 60
        assert extractor.config.language == "es"
        assert extractor.config.keep_article_html is False
        assert extractor.config.fetch_images is False
        assert extractor.config.http_success_only is False
        assert extractor.settings.EXTRACTION_MAX_RETRIES == 5
        assert extractor.settings.EXTRACTION_RETRY_BASE_DELAY == 0.5
        assert extractor.settings.EXTRACTION_RETRY_MULTIPLIER == 3.0
    
    def test_extract_title_with_fallback_strategies(self, extractor, mock_article):
        """Test title extraction with fallback to meta title."""
        # Test primary title extraction
        result = extractor._extract_title(mock_article)
        assert result == "Test Article Title"
        
        # Test fallback to meta title when primary is empty
        mock_article.title = ""
        result = extractor._extract_title(mock_article)
        assert result == "Meta Title"
        
        # Test no title found
        mock_article.title = ""
        mock_article.meta_data = {}
        result = extractor._extract_title(mock_article)
        assert result is None
    
    def test_extract_content_with_length_validation(self, extractor, mock_article):
        """Test content extraction with minimum length validation."""
        # Test valid content
        result = extractor._extract_content(mock_article)
        assert result is not None
        assert len(result) > 50
        
        # Test short content (should be rejected)
        mock_article.text = "Short"
        result = extractor._extract_content(mock_article)
        assert result is None
        
        # Test empty content
        mock_article.text = ""
        result = extractor._extract_content(mock_article)
        assert result is None
    
    def test_extract_author_with_multiple_format_handling(self, extractor, mock_article):
        """Test author extraction with multiple format handling."""
        # Test list of authors
        result = extractor._extract_author(mock_article)
        assert result == "John Doe, Jane Smith"
        
        # Test single author as string
        mock_article.authors = "Single Author"
        result = extractor._extract_author(mock_article)
        assert result == "Single Author"
        
        # Test empty authors
        mock_article.authors = []
        result = extractor._extract_author(mock_article)
        assert result is None
    
    def test_extract_publish_date_with_parsing_and_validation(self, extractor, mock_article):
        """Test publish_date extraction with parsing and validation."""
        # Test datetime object
        result = extractor._extract_publish_date(mock_article)
        assert result == datetime(2023, 10, 15, 14, 30, 0)
        
        # Test string parsing
        with patch('dateutil.parser.parse', return_value=datetime(2023, 12, 1)):
            mock_article.publish_date = "2023-12-01"
            result = extractor._extract_publish_date(mock_article)
            assert result == datetime(2023, 12, 1)
        
        # Test invalid date
        mock_article.publish_date = "invalid-date"
        with patch('dateutil.parser.parse', side_effect=ValueError("Invalid date")):
            result = extractor._extract_publish_date(mock_article)
            assert result is None
    
    def test_extract_image_url_with_url_validation(self, extractor, mock_article):
        """Test image_url extraction with URL validation."""
        # Test valid image URL
        result = extractor._extract_image_url(mock_article)
        assert result == "https://example.com/image.jpg"
        
        # Test URL without extension (should still be valid)
        mock_article.top_image = "https://example.com/dynamic-image"
        result = extractor._extract_image_url(mock_article)
        assert result == "https://example.com/dynamic-image"
        
        # Test invalid URL (no http/https)
        mock_article.top_image = "not-a-url"
        result = extractor._extract_image_url(mock_article)
        assert result is None
        
        # Test empty image URL
        mock_article.top_image = ""
        result = extractor._extract_image_url(mock_article)
        assert result is None