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
        # JavaScript rendering settings
        settings.ENABLE_JAVASCRIPT_RENDERING = True
        settings.PLAYWRIGHT_HEADLESS = True
        settings.PLAYWRIGHT_TIMEOUT = 30
        settings.PLAYWRIGHT_WAIT_TIME = 2.0
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

    @pytest.mark.asyncio
    async def test_javascript_rendering_disabled(self, extractor):
        """Test JavaScript rendering when disabled in settings."""
        # Disable JavaScript rendering
        extractor.settings.ENABLE_JAVASCRIPT_RENDERING = False

        test_url = "https://example.com/js-article"
        correlation_id = "test-123"

        result = await extractor._extract_with_javascript_rendering(test_url, correlation_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_javascript_rendering_playwright_unavailable(self, extractor):
        """Test JavaScript rendering when sync_playwright is not available."""
        test_url = "https://example.com/js-article"
        correlation_id = "test-123"

        with patch('src.core.crawler.extractor.sync_playwright', None):
            result = await extractor._extract_with_javascript_rendering(test_url, correlation_id)

        assert result is None
        extractor.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_javascript_rendering_success(self, extractor, mock_article):
        """Test successful JavaScript rendering extraction."""
        test_url = "https://example.com/js-article"
        correlation_id = "test-123"

        # Mock sync_playwright
        mock_playwright = Mock()
        mock_browser = Mock()
        mock_page = Mock()

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.content.return_value = "<html><body>Rendered content</body></html>"

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright, \
             patch('src.core.crawler.extractor.Article') as MockArticle, \
             patch('time.sleep'):

            # Configure sync_playwright mock
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_sync_playwright.return_value.__exit__.return_value = None

            # Configure Article mock
            mock_instance = MockArticle.return_value
            mock_instance.set_html = Mock()
            mock_instance.parse = Mock()
            mock_instance.title = "JS Rendered Title"
            mock_instance.text = "JavaScript rendered content with sufficient length for validation requirements."
            mock_instance.authors = ["JS Author"]
            mock_instance.publish_date = datetime(2023, 10, 15, 14, 30, 0)
            mock_instance.top_image = "https://example.com/js-image.jpg"
            mock_instance.meta_data = {}

            result = await extractor._extract_with_javascript_rendering(test_url, correlation_id)

        assert result is not None
        assert result["title"] == "JS Rendered Title"
        assert "JavaScript rendered content" in result["content"]
        assert result["author"] == "JS Author"

        # Verify JavaScript rendering was attempted
        mock_playwright.chromium.launch.assert_called_once_with(headless=True)
        mock_page.goto.assert_called_once_with(test_url)
        mock_page.set_default_timeout.assert_called_once_with(30000)
        mock_page.content.assert_called_once()
        mock_browser.close.assert_called_once()

        # Verify Article was configured with rendered HTML
        mock_instance.set_html.assert_called_once_with("<html><body>Rendered content</body></html>")
        mock_instance.parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_javascript_rendering_failure(self, extractor):
        """Test JavaScript rendering failure scenarios."""
        test_url = "https://example.com/js-error-article"
        correlation_id = "test-123"

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright:
            # Simulate playwright failure
            mock_sync_playwright.side_effect = Exception("Playwright browser launch failed")

            result = await extractor._extract_with_javascript_rendering(test_url, correlation_id)

        assert result is None
        extractor.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_fallback_to_javascript_rendering(self, extractor, mock_article):
        """Test fallback to JavaScript rendering when standard extraction fails."""
        test_url = "https://example.com/fallback-article"

        with patch('src.core.crawler.extractor.Article') as MockArticle:
            # Make standard extraction fail consistently
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock(side_effect=Exception("Standard extraction failed"))

            # Mock JavaScript rendering success
            with patch.object(extractor, '_extract_with_javascript_rendering') as mock_js_extraction:
                mock_js_extraction.return_value = {
                    "title": "Fallback Success",
                    "content": "Content extracted via JavaScript rendering fallback mechanism.",
                    "author": "Fallback Author",
                    "publish_date": None,
                    "image_url": None,
                    "source_url": test_url,
                    "url_hash": "test-hash",
                    "content_hash": "test-content-hash",
                    "extracted_at": datetime.now()
                }

                result = await extractor.extract_article_metadata(test_url)

        assert result is not None
        assert result["title"] == "Fallback Success"
        assert "JavaScript rendering fallback" in result["content"]

        # Verify fallback was triggered
        mock_js_extraction.assert_called_once()
        # Check that fallback logging was called - the actual parameters may vary
        assert any("Standard extraction failed, attempting JavaScript rendering fallback" in str(call)
                   for call in extractor.logger.info.call_args_list)

    @pytest.mark.asyncio
    async def test_both_standard_and_javascript_rendering_fail(self, extractor):
        """Test scenario where both standard extraction and JavaScript rendering fail."""
        test_url = "https://example.com/total-failure-article"

        with patch('src.core.crawler.extractor.Article') as MockArticle:
            # Make standard extraction fail
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock(side_effect=Exception("Standard extraction failed"))

            # Make JavaScript rendering also fail
            with patch.object(extractor, '_extract_with_javascript_rendering') as mock_js_extraction:
                mock_js_extraction.side_effect = Exception("JavaScript rendering failed")

                result = await extractor.extract_article_metadata(test_url)

        assert result is None

        # Verify both methods were attempted
        mock_js_extraction.assert_called_once()
        # Check that fallback failure logging was called
        assert any("JavaScript rendering fallback also failed" in str(call)
                   for call in extractor.logger.error.call_args_list)

    @pytest.mark.asyncio
    async def test_google_news_url_detection(self, extractor):
        """Test Google News URL detection in extract_article_metadata."""
        google_news_url = "https://news.google.com/articles/test123"

        with patch.object(extractor, '_extract_google_news_with_playwright') as mock_google_news:
            mock_google_news.return_value = {
                "title": "Google News Article",
                "content": "Content extracted from Google News URL",
                "source_url": google_news_url,
                "extraction_method": "google_news_playwright"
            }

            result = await extractor.extract_article_metadata(google_news_url)

        assert result is not None
        assert result["extraction_method"] == "google_news_playwright"
        mock_google_news.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_articles_batch_with_mixed_urls(self, extractor):
        """Test batch extraction with mixed Google News and regular URLs."""
        urls = [
            "https://news.google.com/articles/test1",
            "https://example.com/regular-article",
            "https://news.google.com/articles/test2",
            "https://another-site.com/news"
        ]

        with patch.object(extractor, '_extract_google_news_batch') as mock_google_batch, \
             patch.object(extractor, 'extract_article_metadata') as mock_regular:

            # Mock Google News batch results
            mock_google_batch.return_value = [
                {"title": "Google News 1", "extraction_method": "google_news_playwright"},
                {"title": "Google News 2", "extraction_method": "google_news_playwright"}
            ]

            # Mock regular extraction results
            mock_regular.side_effect = [
                {"title": "Regular Article 1", "extraction_method": "standard"},
                {"title": "Regular Article 2", "extraction_method": "standard"}
            ]

            results = await extractor.extract_articles_batch(urls)

        assert len(results) == 4
        mock_google_batch.assert_called_once()
        assert mock_regular.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_google_news_batch_processing(self, extractor):
        """Test Google News batch processing with batches of 10."""
        google_urls = [f"https://news.google.com/articles/test{i}" for i in range(25)]

        with patch.object(extractor, '_process_batch_with_single_browser') as mock_process_batch, \
             patch('asyncio.sleep') as mock_sleep:

            # Mock batch processing results
            mock_process_batch.side_effect = [
                # First batch (10 URLs)
                [{"title": f"Article {i}", "extraction_success": True} for i in range(10)],
                # Second batch (10 URLs)
                [{"title": f"Article {i}", "extraction_success": True} for i in range(10, 20)],
                # Third batch (5 URLs)
                [{"title": f"Article {i}", "extraction_success": True} for i in range(20, 25)]
            ]

            results = await extractor._extract_google_news_batch(google_urls)

        assert len(results) == 25
        assert mock_process_batch.call_count == 3
        # Should have 2 delays between 3 batches
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batch_with_single_browser_success(self, extractor):
        """Test single browser multi-tab processing success."""
        test_urls = [f"https://news.google.com/articles/test{i}" for i in range(3)]

        # Mock sync_playwright
        mock_playwright = Mock()
        mock_browser = Mock()
        mock_pages = [Mock() for _ in range(3)]

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.side_effect = mock_pages

        # Configure page mocks for successful redirects
        for i, page in enumerate(mock_pages):
            page.goto = AsyncMock()
            page.route = AsyncMock()
            page.set_extra_http_headers = Mock()
            page.url = f"https://redirected-site{i}.com/article"
            page.close = Mock()

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright, \
             patch.object(extractor, '_extract_with_newspaper') as mock_newspaper, \
             patch('asyncio.sleep') as mock_sleep:

            # Configure sync_playwright context manager
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_sync_playwright.return_value.__exit__.return_value = None

            # Mock newspaper extraction
            mock_newspaper.side_effect = [
                {"title": f"Article {i}", "extraction_success": True} for i in range(3)
            ]

            results = await extractor._process_batch_with_single_browser(test_urls)

        assert len(results) == 3
        assert all(result.get("extraction_method") == "google_news_playwright" for result in results)
        mock_browser.close.assert_called_once()
        # Should have 2 delays between 3 tabs
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batch_with_single_browser_no_redirect(self, extractor):
        """Test handling of URLs that don't redirect from Google News."""
        test_urls = ["https://news.google.com/articles/no-redirect"]

        # Mock sync_playwright
        mock_playwright = Mock()
        mock_browser = Mock()
        mock_page = Mock()

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Configure page mock for no redirect (URL stays the same)
        mock_page.goto = AsyncMock()
        mock_page.route = AsyncMock()
        mock_page.set_extra_http_headers = Mock()
        mock_page.url = test_urls[0]  # Same URL = no redirect
        mock_page.close = Mock()

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright, \
             patch('asyncio.sleep'):

            # Configure sync_playwright context manager
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_sync_playwright.return_value.__exit__.return_value = None

            results = await extractor._process_batch_with_single_browser(test_urls)

        assert len(results) == 1
        assert results[0]["extraction_success"] == False
        assert results[0]["extraction_error"] == "No redirect from Google News URL"
        assert results[0]["extraction_method"] == "google_news_no_redirect"

    @pytest.mark.asyncio
    async def test_process_batch_with_single_browser_playwright_unavailable(self, extractor):
        """Test batch processing when sync_playwright is not available."""
        test_urls = ["https://news.google.com/articles/test1"]

        with patch('src.core.crawler.extractor.sync_playwright', None):
            results = await extractor._process_batch_with_single_browser(test_urls)

        assert len(results) == 0
        extractor.logger.error.assert_called_with("sync_playwright not available for Google News extraction")

    @pytest.mark.asyncio
    async def test_process_batch_browser_failure(self, extractor):
        """Test handling of browser launch failure."""
        test_urls = ["https://news.google.com/articles/test1", "https://news.google.com/articles/test2"]

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright:
            # Simulate browser failure
            mock_playwright = Mock()
            mock_playwright.chromium.launch.side_effect = Exception("Browser launch failed")
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_sync_playwright.return_value.__exit__.return_value = None

            results = await extractor._process_batch_with_single_browser(test_urls)

        assert len(results) == 2
        assert all(result["extraction_success"] == False for result in results)
        assert all(result["extraction_method"] == "google_news_browser_failed" for result in results)

    @pytest.mark.asyncio
    async def test_process_batch_tab_failure(self, extractor):
        """Test handling of individual tab failures."""
        test_urls = ["https://news.google.com/articles/test1", "https://news.google.com/articles/test2"]

        # Mock sync_playwright
        mock_playwright = Mock()
        mock_browser = Mock()
        mock_page1 = Mock()
        mock_page2 = Mock()

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.side_effect = [mock_page1, mock_page2]

        # First tab fails, second succeeds
        mock_page1.goto = AsyncMock(side_effect=Exception("Tab 1 failed"))
        mock_page1.route = AsyncMock()
        mock_page1.set_extra_http_headers = Mock()
        mock_page1.close = Mock()

        mock_page2.goto = AsyncMock()
        mock_page2.route = AsyncMock()
        mock_page2.set_extra_http_headers = Mock()
        mock_page2.url = "https://redirected.com/article"
        mock_page2.close = Mock()

        with patch('src.core.crawler.extractor.sync_playwright') as mock_sync_playwright, \
             patch.object(extractor, '_extract_with_newspaper') as mock_newspaper, \
             patch('asyncio.sleep'):

            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_sync_playwright.return_value.__exit__.return_value = None

            mock_newspaper.return_value = {"title": "Success", "extraction_success": True}

            results = await extractor._process_batch_with_single_browser(test_urls)

        assert len(results) == 2
        assert results[0]["extraction_success"] == False
        assert results[0]["extraction_method"] == "google_news_tab_failed"
        assert results[1]["extraction_method"] == "google_news_playwright"

    @pytest.mark.asyncio
    async def test_anti_detection_delays(self, extractor):
        """Test anti-detection delays between tabs and batches."""
        test_urls = [f"https://news.google.com/articles/test{i}" for i in range(2)]

        with patch('asyncio.sleep') as mock_sleep, \
             patch('random.randint') as mock_randint:

            mock_randint.return_value = 2  # Fixed delay for testing

            # Test batch delay
            await extractor._extract_google_news_batch(test_urls * 11)  # 22 URLs = 3 batches

            # Should have delays between batches
            batch_delay_calls = [call for call in mock_sleep.call_args_list if call[0][0] >= 5]
            assert len(batch_delay_calls) >= 2  # At least 2 batch delays

    @pytest.mark.asyncio
    async def test_extract_google_news_with_playwright_single_url(self, extractor):
        """Test single Google News URL extraction wrapper."""
        test_url = "https://news.google.com/articles/test1"
        correlation_id = "test-123"

        with patch.object(extractor, '_process_batch_with_single_browser') as mock_batch:
            mock_batch.return_value = [{
                "title": "Test Article",
                "extraction_success": True,
                "final_redirected_url": "https://example.com/article"
            }]

            result = await extractor._extract_google_news_with_playwright(test_url, correlation_id)

        assert result is not None
        assert result["title"] == "Test Article"
        mock_batch.assert_called_once_with([test_url])

    @pytest.mark.asyncio
    async def test_extract_with_newspaper_success(self, extractor, mock_article):
        """Test newspaper extraction wrapper."""
        test_url = "https://example.com/article"

        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.title = mock_article.title
            mock_instance.text = mock_article.text
            mock_instance.authors = mock_article.authors
            mock_instance.publish_date = mock_article.publish_date
            mock_instance.top_image = mock_article.top_image
            mock_instance.meta_data = mock_article.meta_data

            result = await extractor._extract_with_newspaper(test_url)

        assert result is not None
        assert result["extraction_success"] == True
        assert result["title"] == "Test Article Title"

    @pytest.mark.asyncio
    async def test_extract_with_newspaper_failure(self, extractor):
        """Test newspaper extraction wrapper failure."""
        test_url = "https://example.com/failed-article"

        with patch('src.core.crawler.extractor.Article') as MockArticle:
            mock_instance = MockArticle.return_value
            mock_instance.download = Mock(side_effect=Exception("Download failed"))

            result = await extractor._extract_with_newspaper(test_url)

        assert result is None
        extractor.logger.error.assert_called()